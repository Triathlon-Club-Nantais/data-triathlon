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
  entrees = [entree(), entree({ id: 2, value: "tri club nantais" })],
  isLoading = false,
} = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CounterScopeCard
        kind={kind}
        titre="Libellés comptés comme club"
        nom="libellés du club"
        regle="La comparaison ignore la casse."
        entrees={entrees}
        isLoading={isLoading}
        libelleChamp="Nouveau libellé"
        placeholder="tcn 44"
        descriptionListeVide="Aucun libellé : plus aucun résultat n'est du club."
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("CounterScopeCard", () => {
  it("liste les entrées avec leur provenance", () => {
    afficher();

    expect(screen.getByText("tcn")).toBeInTheDocument();
    expect(screen.getAllByText(/ajouté par marie dupont/i)).toHaveLength(2);
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

    expect(screen.getByText("Discipline inconnue")).toBeInTheDocument();
  });

  it("ne signale rien quand la discipline est connue", () => {
    afficher({ kind: "disciplines", entrees: [entree({ value: "trail" })] });

    expect(screen.queryByText("Discipline inconnue")).not.toBeInTheDocument();
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
    afficher({
      entrees: [entree({ value: "triathlon club nantais" }), entree({ id: 2, value: "tcn" })],
    });

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

  it("distingue une liste vide d'un chargement", () => {
    afficher({ entrees: [] });

    expect(screen.getByText(/cette liste est vide/i)).toBeInTheDocument();
  });

  it("dit ce que le vide signifie pour cette liste-ci, pas seulement qu'elle est vide", () => {
    afficher({ entrees: [] });

    expect(
      screen.getByText(/plus aucun résultat n'est du club/i),
    ).toBeInTheDocument();
  });

  it("annonce le chargement aux aides techniques", () => {
    afficher({ isLoading: true, entrees: undefined });

    expect(screen.getByRole("status")).toHaveTextContent(/chargement de la liste/i);
  });

  it("refuse le retrait du dernier libellé du club, en disant pourquoi avant le clic", async () => {
    afficher({ entrees: [entree()] });

    expect(screen.getByRole("button", { name: /retirer « tcn »/i })).toBeDisabled();
    expect(screen.getByText(/dernier libellé/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retirer « tcn »/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("laisse retirer la dernière discipline — le serveur ne l'interdit pas", () => {
    afficher({ kind: "disciplines", entrees: [entree({ value: "trail" })] });

    expect(screen.getByRole("button", { name: /retirer « trail »/i })).toBeEnabled();
  });

  it("nomme la liste dans le toast, les deux cartes étant côte à côte", async () => {
    addCounterScopeEntry.mockResolvedValue(entree({ value: "tcn 44" }));
    afficher();

    await userEvent.type(screen.getByLabelText(/nouveau libellé/i), "tcn 44");
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("« tcn 44 » ajouté aux libellés du club."),
    );
  });

  it("repose le focus sur le champ d'ajout après un retrait", async () => {
    removeCounterScopeEntry.mockResolvedValue(undefined);
    afficher();

    await userEvent.click(screen.getByRole("button", { name: /retirer « tcn »/i }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(within(dialogue).getByRole("button", { name: /^retirer$/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/nouveau libellé/i)).toHaveFocus(),
    );
  });

  it("explique « Discipline inconnue » en texte, pas dans une infobulle native", () => {
    afficher({
      kind: "disciplines",
      entrees: [entree({ value: "kayak-polo", is_known: false })],
    });

    expect(screen.getByText(/ne correspond à aucune discipline connue/i)).toBeInTheDocument();
    expect(screen.getByText("Discipline inconnue")).not.toHaveAttribute("title");
  });
});
