import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";

const api = vi.hoisted(() => ({
  listIgnoredIdentityPairs: vi.fn(),
  unignoreIdentityPair: vi.fn(),
  listConfirmedIdentityClubs: vi.fn(),
  unconfirmIdentityClub: vi.fn(),
  listIgnoredCourseDuplicates: vi.fn(),
  unignoreCourseDuplicate: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: api };
});
vi.mock("sonner", () => ({ toast: { success: api.toastSuccess, error: api.toastError } }));

import { ApiError } from "@/lib/api/client";
import { IdentityArbitrations, IgnoredCourseDuplicates } from "./ArbitrationUndoList";

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>{ui}</DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.listIgnoredIdentityPairs.mockResolvedValue({
    pairs: [
      {
        id: 7,
        ignored_at: "2026-10-07T09:00:00",
        automatic: false,
        athletes: [
          { id: 1, nom: "DUPONT", prenom: "Jean" },
          { id: 2, nom: "JEAN", prenom: "Dupont" },
        ],
      },
    ],
  });
  api.listConfirmedIdentityClubs.mockResolvedValue({
    clubs: [
      {
        id: 3, athlete_id: 5, nom: "MARTIN", prenom: "Thomas",
        club_key: "vendometriathlon", confirmed_at: "2026-10-07T09:00:00",
      },
    ],
  });
  api.listIgnoredCourseDuplicates.mockResolvedValue({
    pairs: [
      {
        id: 9,
        ignored_at: "2026-10-07T09:00:00",
        courses: [
          { id: 38, name: "Mesquer", event_date: "2026-06-13" },
          { id: 39, name: "Mesquer relais", event_date: "2026-06-13" },
        ],
      },
    ],
  });
});

describe("IdentityArbitrations", () => {
  it("replie les deux listes par défaut et annonce leur taille", async () => {
    renderWithProviders(<IdentityArbitrations />);

    const pairs = await screen.findByText("Paires écartées (1)");
    const clubs = await screen.findByText("Clubs confirmés (1)");
    expect(pairs.closest("details")).not.toHaveAttribute("open");
    expect(clubs.closest("details")).not.toHaveAttribute("open");
  });

  it("annule la mise à l'écart d'une paire après une confirmation qui prévient de la fusion", async () => {
    api.unignoreIdentityPair.mockResolvedValue(undefined);
    renderWithProviders(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Paires écartées (1)"));

    const row = screen.getByText(/DUPONT Jean et JEAN Dupont/).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: /annuler/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/prochaine reprise pourra fusionner/i)).toBeInTheDocument();
    expect(api.unignoreIdentityPair).not.toHaveBeenCalled();
    await confirmerDansLeDialog(/annuler la mise à l'écart/i);

    expect(api.unignoreIdentityPair).toHaveBeenCalledWith(7);
    expect(api.toastSuccess).toHaveBeenCalledWith(expect.not.stringMatching(/revient dans la revue/));
  });

  it("n'annule rien si la confirmation est refusée", async () => {
    renderWithProviders(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Paires écartées (1)"));

    await userEvent.click(screen.getAllByRole("button", { name: /annuler/i })[0]);
    await confirmerDansLeDialog(/renoncer/i);

    expect(api.unignoreIdentityPair).not.toHaveBeenCalled();
  });

  it("signale une paire posée par l'import", async () => {
    api.listIgnoredIdentityPairs.mockResolvedValue({
      pairs: [
        {
          id: 8, ignored_at: "2026-10-07T09:00:00", automatic: true,
          athletes: [{ id: 1, nom: "A", prenom: "B" }, { id: 2, nom: "C", prenom: "D" }],
        },
      ],
    });
    renderWithProviders(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Paires écartées (1)"));

    expect(screen.getByText(/posée par l'import/i)).toBeInTheDocument();
  });

  it("annule la confirmation d'un club", async () => {
    api.unconfirmIdentityClub.mockResolvedValue(undefined);
    renderWithProviders(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Clubs confirmés (1)"));

    const row = screen.getByText(/MARTIN Thomas/).closest("li")!;
    expect(within(row).getByText(/vendometriathlon/)).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: /annuler/i }));

    expect(api.unconfirmIdentityClub).toHaveBeenCalledWith(3);
  });

  it("dit l'échec d'une annulation", async () => {
    api.unignoreIdentityPair.mockRejectedValue(new Error("Cette paire n'est pas écartée."));
    renderWithProviders(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Paires écartées (1)"));

    await userEvent.click(screen.getAllByRole("button", { name: /annuler/i })[0]);
    await confirmerDansLeDialog(/annuler la mise à l'écart/i);

    expect(api.toastError).toHaveBeenCalledWith("Cette paire n'est pas écartée.");
  });

  it("dit « accès refusé » sur un 403 au lieu de disparaître", async () => {
    api.listIgnoredIdentityPairs.mockRejectedValue(new ApiError(403, "Refusé"));
    renderWithProviders(<IdentityArbitrations />);

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });
});

describe("IgnoredCourseDuplicates", () => {
  it("liste les paires d'épreuves écartées, repliées, et annule l'une", async () => {
    api.unignoreCourseDuplicate.mockResolvedValue(undefined);
    renderWithProviders(<IgnoredCourseDuplicates />);

    const summary = await screen.findByText("Paires écartées (1)");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(summary);
    await userEvent.click(screen.getByRole("button", { name: /annuler/i }));

    expect(screen.getByText(/Mesquer \(n° 38\) et Mesquer relais \(n° 39\)/)).toBeInTheDocument();
    expect(api.unignoreCourseDuplicate).toHaveBeenCalledWith(9);
  });

  it("dit qu'aucune paire n'est écartée", async () => {
    api.listIgnoredCourseDuplicates.mockResolvedValue({ pairs: [] });
    renderWithProviders(<IgnoredCourseDuplicates />);

    await userEvent.click(await screen.findByText("Paires écartées (0)"));

    expect(screen.getByText(/aucune paire écartée/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403 au lieu de disparaître", async () => {
    api.listIgnoredCourseDuplicates.mockRejectedValue(new ApiError(403, "Refusé"));
    renderWithProviders(<IgnoredCourseDuplicates />);

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });
});
