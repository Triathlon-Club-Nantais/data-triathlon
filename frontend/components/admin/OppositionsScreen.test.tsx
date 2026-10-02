import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Opposition } from "@/lib/types";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { OppositionsScreen } from "./OppositionsScreen";

const { listOppositions, previewOpposition, applyOpposition } = vi.hoisted(() => ({
  listOppositions: vi.fn(),
  previewOpposition: vi.fn(),
  applyOpposition: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listOppositions, previewOpposition, applyOpposition } };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const DANS_LE_DELAI: Opposition = {
  id: 1,
  requested_on: "2026-09-20",
  applied_at: "2026-10-01T16:00:00Z",
  delay_days: 11,
  overdue: false,
  applied_by_name: "Admin",
  anonymised_count: 4,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <OppositionsScreen />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("OppositionsScreen (#334)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listOppositions.mockResolvedValue([DANS_LE_DELAI]);
    previewOpposition.mockResolvedValue({ athletes: 0, results: 0, already_opposed: false });
    applyOpposition.mockResolvedValue({ ...DANS_LE_DELAI, id: 2 });
  });

  it("liste chaque opposition avec ses dates, son délai, son auteur et ses résultats, sans nom", async () => {
    afficher();

    const ligne = (await screen.findByText("11 jours")).closest("tr")!;
    expect(within(ligne).getByText("20/09/2026")).toBeInTheDocument();
    expect(within(ligne).getByText("01/10/2026")).toBeInTheDocument();
    expect(within(ligne).getByText("Admin")).toBeInTheDocument();
    expect(within(ligne).getByText("4")).toBeInTheDocument();
  });

  it("signale une opposition appliquée au-delà du délai d'un mois", async () => {
    listOppositions.mockResolvedValue([{ ...DANS_LE_DELAI, delay_days: 45, overdue: true }]);
    afficher();

    expect(await screen.findByText(/hors délai/i)).toBeInTheDocument();
  });

  it("dit qu'aucune opposition n'a encore été reçue", async () => {
    listOppositions.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/aucune opposition/i)).toBeInTheDocument();
  });

  it("enregistre une opposition par nom après confirmation chiffrée", async () => {
    previewOpposition.mockResolvedValue({ athletes: 1, results: 3, already_opposed: false });
    const user = userEvent.setup();
    afficher();

    await user.type(await screen.findByLabelText("Nom"), "Dupont");
    await user.type(screen.getByLabelText("Prénom"), "Jean");
    const date = screen.getByLabelText(/date de la demande/i);
    await user.clear(date);
    await user.type(date, "2026-09-25");
    await user.click(screen.getByRole("button", { name: "Enregistrer l'opposition" }));

    const dialogue = await screen.findByRole("dialog");
    expect(previewOpposition).toHaveBeenCalledWith({ nom: "Dupont", prenom: "Jean" });
    expect(dialogue).toHaveTextContent(/3 résultats/);
    await user.click(within(dialogue).getByRole("button", { name: /anonymiser/i }));

    await waitFor(() =>
      expect(applyOpposition).toHaveBeenCalledWith({ nom: "Dupont", prenom: "Jean", requested_on: "2026-09-25" }),
    );
  });
});
