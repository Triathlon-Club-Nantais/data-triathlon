import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import type { MemberEmailsSeason } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { importMemberEmails, addMemberEmail, removeMemberEmail } = vi.hoisted(() => ({
  importMemberEmails: vi.fn(),
  addMemberEmail: vi.fn(),
  removeMemberEmail: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { importMemberEmails, addMemberEmail, removeMemberEmail } };
});

import { MemberEmailsPanel } from "./MemberEmailsPanel";
import { DangerConfirmProvider } from "./DangerConfirm";
import { confirmerDansLeDialog } from "./__tests__/dangerConfirm";

const SAISON: MemberEmailsSeason = {
  season: 2026,
  counting_season: 2026,
  seasons: [2026, 2025],
  entries: [
    { id: 1, email: "anne@exemple.fr", season: 2026, source: "import", created_at: "2026-10-01T10:00:00Z" },
    { id: 2, email: "paul@exemple.fr", season: 2026, source: "manual", created_at: "2026-10-02T10:00:00Z" },
  ],
};

function afficher(props: Partial<Parameters<typeof MemberEmailsPanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onSeasonChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <MemberEmailsPanel season={2026} onSeasonChange={onSeasonChange} data={SAISON} isLoading={false} {...props} />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
  return { onSeasonChange };
}

describe("MemberEmailsPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lays the add form out on its container width, not the viewport (#1779)", () => {
    afficher();

    const formulaire = screen.getByLabelText("Adresse à ajouter").closest("form");
    expect(formulaire?.parentElement).toHaveClass("@container");
    expect(formulaire?.className).toContain("@xl:flex-row");
    expect(formulaire?.className).not.toContain("sm:");
  });

  it("lists the season's addresses with their origin and the counting season", () => {
    afficher();

    expect(screen.getByText("anne@exemple.fr")).toBeInTheDocument();
    expect(screen.getByText("paul@exemple.fr")).toBeInTheDocument();
    expect(screen.getByText("Ajoutée à la main")).toBeInTheDocument();
    expect(screen.getByText(/2 adresses/)).toBeInTheDocument();
    expect(screen.getByText(/saison qui compte aujourd'hui : saison 2026/i)).toBeInTheDocument();
  });

  it("explains that the previous season still counts while the current one is empty", () => {
    afficher({ data: { ...SAISON, counting_season: 2025, entries: [] } });

    expect(screen.getByText(/saison qui compte aujourd'hui : saison 2025/i)).toBeInTheDocument();
    expect(screen.getByText(/aucune adresse pour cette saison/i)).toBeInTheDocument();
  });

  it("shows a skeleton while loading", () => {
    afficher({ data: undefined, isLoading: true });

    expect(screen.queryByText("anne@exemple.fr")).not.toBeInTheDocument();
    expect(screen.getByTestId("member-emails-loading")).toBeInTheDocument();
  });

  it("imports a file and shows the report", async () => {
    importMemberEmails.mockResolvedValue({ season: 2026, added: 280, removed: 4, unchanged: 12, ignored: 3 });
    afficher();

    const fichier = new File(["email\na@exemple.fr\n"], "export.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText(/export assoconnect/i), fichier);
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));

    await waitFor(() => expect(importMemberEmails).toHaveBeenCalledWith(2026, fichier));
    expect(
      await screen.findByText("280 ajoutées, 4 retirées, 12 inchangées, 3 lignes ignorées."),
    ).toBeInTheDocument();
  });

  it("forgets the import report and the chosen file when the season changes", async () => {
    importMemberEmails.mockResolvedValue({ season: 2026, added: 1, removed: 0, unchanged: 0, ignored: 0 });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const panneau = (season: number) => (
      <QueryClientProvider client={client}>
        <DangerConfirmProvider>
          <MemberEmailsPanel season={season} onSeasonChange={vi.fn()} data={SAISON} isLoading={false} />
        </DangerConfirmProvider>
      </QueryClientProvider>
    );
    const { rerender } = render(panneau(2026));
    await userEvent.upload(screen.getByLabelText(/export assoconnect/i), new File(["x"], "x.csv"));
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));
    expect(await screen.findByText(/1 ajoutée/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText(/export assoconnect/i), new File(["y"], "y.csv"));

    rerender(panneau(2025));

    expect(screen.queryByText(/1 ajoutée/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importer" })).toBeDisabled();
  });

  it("says that a manual address alone does not switch the counting season", () => {
    afficher();

    expect(screen.getByText(/dès qu.elle a une adresse importée/i)).toBeInTheDocument();
  });

  it("shows the server's French message when the import is refused", async () => {
    importMemberEmails.mockRejectedValue(new Error("Colonne d'adresses e-mail introuvable dans ce fichier."));
    afficher();

    await userEvent.upload(screen.getByLabelText(/export assoconnect/i), new File(["x"], "x.csv"));
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Colonne d'adresses e-mail introuvable dans ce fichier."),
    );
  });

  it("adds an address by hand to the selected season", async () => {
    addMemberEmail.mockResolvedValue({ id: 3, email: "zoe@exemple.fr", season: 2026, source: "manual", created_at: "" });
    afficher();

    await userEvent.type(screen.getByLabelText(/adresse à ajouter/i), "zoe@exemple.fr");
    await userEvent.click(screen.getByRole("button", { name: "Ajouter" }));

    await waitFor(() => expect(addMemberEmail).toHaveBeenCalledWith("zoe@exemple.fr", 2026));
    expect(toast.success).toHaveBeenCalled();
  });

  it("removes an address only after confirmation", async () => {
    removeMemberEmail.mockResolvedValue(null);
    afficher();

    await userEvent.click(screen.getByRole("button", { name: "Retirer anne@exemple.fr" }));
    expect(removeMemberEmail).not.toHaveBeenCalled();
    await confirmerDansLeDialog("Retirer");

    await waitFor(() => expect(removeMemberEmail).toHaveBeenCalledWith(1));
  });
});
