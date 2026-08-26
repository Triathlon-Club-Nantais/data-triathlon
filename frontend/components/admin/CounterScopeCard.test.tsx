import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CounterScopeEntry, ScopeKind } from "@/lib/types";

const { addCounterScopeEntry, removeCounterScopeEntry, toastError, toastSuccess } =
  vi.hoisted(() => ({
    addCounterScopeEntry: vi.fn(),
    removeCounterScopeEntry: vi.fn(),
    toastError: vi.fn(),
    toastSuccess: vi.fn(),
  }));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { addCounterScopeEntry, removeCounterScopeEntry },
  };
});

import { CounterScopeCard } from "./CounterScopeCard";

function entree(surcharge: Partial<CounterScopeEntry> = {}): CounterScopeEntry {
  return {
    id: 1,
    value: "tcn",
    is_known: true,
    created_at: "2026-08-20T10:00:00Z",
    created_by: "Marie Dupont",
    ...surcharge,
  };
}

function afficher({
  kind = "club-labels" as ScopeKind,
  entrees = [entree()],
  isLoading = false,
  error = null as Error | null,
} = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CounterScopeCard
        kind={kind}
        titre="Libellés du club"
        regle="La comparaison ignore la casse."
        entrees={entrees}
        isLoading={isLoading}
        error={error}
        libelleChamp="Nouveau libellé"
        placeholder="TCN 44"
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("CounterScopeCard", () => {
  it("liste les entrées avec leur provenance", () => {
    afficher();

    expect(screen.getByText("tcn")).toBeInTheDocument();
    expect(screen.getByText(/ajouté par marie dupont/i)).toBeInTheDocument();
  });

  it("rend « Configuration initiale » pour une entrée sans auteur", () => {
    afficher({ entrees: [entree({ created_by: null })] });

    expect(screen.getByText("Configuration initiale")).toBeInTheDocument();
  });

  it("signale une discipline hors nomenclature sans la distinguer autrement", () => {
    afficher({
      kind: "disciplines",
      entrees: [entree({ value: "kayak-polo", is_known: false })],
    });

    expect(screen.getByText(/discipline inconnue/i)).toBeInTheDocument();
  });

  it("ne signale rien quand la discipline est connue", () => {
    afficher({ kind: "disciplines", entrees: [entree({ value: "trail" })] });

    expect(screen.queryByText(/discipline inconnue/i)).not.toBeInTheDocument();
  });

  it("ajoute une entrée et vide le champ", async () => {
    addCounterScopeEntry.mockResolvedValue(entree({ value: "tcn 44" }));
    afficher();

    await userEvent.type(screen.getByLabelText(/nouveau libellé/i), "TCN 44");
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(addCounterScopeEntry).toHaveBeenCalledWith("club-labels", "TCN 44"),
    );
    expect(screen.getByLabelText(/nouveau libellé/i)).toHaveValue("");
  });

  it("laisse le bouton d'ajout inerte tant que le champ est vide", () => {
    afficher();

    expect(screen.getByRole("button", { name: /ajouter/i })).toBeDisabled();
  });

  it("montre le refus du serveur plutôt qu'un succès muet", async () => {
    addCounterScopeEntry.mockRejectedValue(
      new ApiError(409, "« tcn » figure déjà dans la liste."),
    );
    afficher();

    await userEvent.type(screen.getByLabelText(/nouveau libellé/i), "tcn");
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("« tcn » figure déjà dans la liste."),
    );
  });

  it("demande confirmation avant de retirer", async () => {
    afficher();

    await userEvent.click(screen.getByRole("button", { name: /retirer « tcn »/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(removeCounterScopeEntry).not.toHaveBeenCalled();
  });

  it("retire l'entrée une fois la confirmation validée", async () => {
    removeCounterScopeEntry.mockResolvedValue(undefined);
    afficher();

    await userEvent.click(screen.getByRole("button", { name: /retirer « tcn »/i }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialogue).getByRole("button", { name: /^retirer$/i }),
    );

    await waitFor(() =>
      expect(removeCounterScopeEntry).toHaveBeenCalledWith("club-labels", 1),
    );
  });

  it("avertit spécifiquement quand le libellé retiré est le nom affiché du club", async () => {
    afficher({ entrees: [entree({ value: "triathlon club nantais" })] });

    await userEvent.click(
      screen.getByRole("button", { name: /retirer « triathlon club nantais »/i }),
    );

    const dialogue = await screen.findByRole("dialog");
    expect(dialogue).toHaveTextContent(/nom affiché du club/i);
  });

  it("n'avertit pas pour un libellé ordinaire", async () => {
    afficher();

    await userEvent.click(screen.getByRole("button", { name: /retirer « tcn »/i }));

    const dialogue = await screen.findByRole("dialog");
    expect(dialogue).not.toHaveTextContent(/nom affiché du club/i);
  });

  it("dit le refus plutôt que d'afficher une liste vide", () => {
    afficher({ entrees: undefined, error: new ApiError(403, "Interdit") });

    expect(screen.getByText(/accès refusé/i)).toBeInTheDocument();
  });

  it("distingue une liste vide d'un chargement", () => {
    afficher({ entrees: [] });

    expect(screen.getByText(/cette liste est vide/i)).toBeInTheDocument();
  });
});
