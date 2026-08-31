import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ClubAlias } from "@/lib/types";

const { addClubAlias, removeClubAlias, toastError, toastSuccess } = vi.hoisted(() => ({
  addClubAlias: vi.fn(),
  removeClubAlias: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { addClubAlias, removeClubAlias } };
});

import { ClubAliasCard } from "./ClubAliasCard";

function entree(surcharge: Partial<ClubAlias> = {}): ClubAlias {
  return {
    id: 1,
    canonical_name: "Racing Club Nantais",
    alias: "racing club nantais",
    created_at: "2026-08-20T10:00:00Z",
    created_by: "Marie Dupont",
    ...surcharge,
  };
}

function afficher({
  entrees = [entree(), entree({ id: 2, alias: "rcn 44" })],
  isLoading = false,
}: { entrees?: ClubAlias[]; isLoading?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ClubAliasCard entrees={entrees} isLoading={isLoading} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("ClubAliasCard", () => {
  it("groupe les alias sous leur nom canonique", () => {
    afficher();

    expect(screen.getByText("Racing Club Nantais")).toBeInTheDocument();
    expect(screen.getByText("racing club nantais")).toBeInTheDocument();
    expect(screen.getByText("rcn 44")).toBeInTheDocument();
  });

  it("affiche deux groupes distincts pour deux noms canoniques", () => {
    afficher({
      entrees: [
        entree({ id: 1, canonical_name: "Racing Club Nantais", alias: "rcn" }),
        entree({ id: 2, canonical_name: "ASPTT", alias: "asptt nantes" }),
      ],
    });

    expect(screen.getByText("Racing Club Nantais")).toBeInTheDocument();
    expect(screen.getByText("ASPTT")).toBeInTheDocument();
  });

  it("dit qu'aucune variante n'est déclarée sur une liste vide", () => {
    afficher({ entrees: [] });

    expect(screen.getByText("Aucune variante déclarée")).toBeInTheDocument();
  });

  it("rend « Configuration initiale » pour une entrée sans auteur", () => {
    afficher({ entrees: [entree({ created_by: null })] });

    expect(screen.getByText("Configuration initiale")).toBeInTheDocument();
  });

  it("ajoute un alias via le formulaire", async () => {
    addClubAlias.mockResolvedValue(entree({ id: 3, alias: "rcn 44 nord" }));
    afficher({ entrees: [] });

    await userEvent.type(screen.getByLabelText(/nom affiché/i), "Racing Club Nantais");
    await userEvent.type(screen.getByLabelText(/libellé brut/i), "RCN 44 NORD");
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(addClubAlias).toHaveBeenCalledWith("Racing Club Nantais", "RCN 44 NORD"),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("retire un alias au clic, sans confirmation", async () => {
    removeClubAlias.mockResolvedValue(undefined);
    afficher({ entrees: [entree({ id: 5, alias: "rcn" })] });

    await userEvent.click(screen.getByRole("button", { name: /retirer « rcn »/i }));

    await waitFor(() => expect(removeClubAlias).toHaveBeenCalledWith(5));
    expect(toastSuccess).toHaveBeenCalled();
  });
});
