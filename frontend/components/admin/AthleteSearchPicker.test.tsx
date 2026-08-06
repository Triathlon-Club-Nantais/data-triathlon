import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AdminAthlete } from "@/lib/types";

const { searchAthletesAdmin } = vi.hoisted(() => ({ searchAthletesAdmin: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { searchAthletesAdmin } };
});

import { AthleteSearchPicker } from "./AthleteSearchPicker";

const PROLIFIQUE: AdminAthlete = {
  id: 1,
  nom: "MARTIN",
  prenom: "Paul",
  birth_date: "1990-01-01",
  gender: "M",
  club: "Triathlon Club Nantais",
  participations: 12,
};

const RARE: AdminAthlete = {
  id: 2,
  nom: "MARTIN",
  prenom: "Paul",
  birth_date: "1985-06-02",
  gender: "M",
  club: "Triathlon Club Nantais",
  participations: 1,
};

function afficher(onSelect = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AthleteSearchPicker selectedId={null} onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return onSelect;
}

describe("AthleteSearchPicker", () => {
  beforeEach(() => searchAthletesAdmin.mockReset());

  it("départage deux homonymes du même club (FR-024)", async () => {
    searchAthletesAdmin.mockResolvedValue([PROLIFIQUE, RARE]);

    afficher();
    await userEvent.type(screen.getByRole("searchbox"), "martin");

    // Sans la date de naissance ni le compte, ces deux fiches seraient
    // indiscernables — et le geste fusionnerait deux personnes distinctes.
    expect(await screen.findByText(/01\/01\/1990|1990-01-01/)).toBeInTheDocument();
    expect(await screen.findByText(/02\/06\/1985|1985-06-02/)).toBeInTheDocument();
    expect(await screen.findByText(/12 résultats/)).toBeInTheDocument();
    expect(await screen.findByText(/1 résultat\b/)).toBeInTheDocument();
  });

  it("remonte la fiche choisie", async () => {
    searchAthletesAdmin.mockResolvedValue([PROLIFIQUE]);

    const onSelect = afficher();
    await userEvent.type(screen.getByRole("searchbox"), "martin");
    await userEvent.click(await screen.findByRole("button", { name: /MARTIN Paul/ }));

    expect(onSelect).toHaveBeenCalledWith(PROLIFIQUE);
  });

  it("ne cherche rien tant que la saisie est vide", async () => {
    afficher();

    expect(searchAthletesAdmin).not.toHaveBeenCalled();
  });

  it("dit qu'aucune fiche ne correspond plutôt que de rester muet", async () => {
    searchAthletesAdmin.mockResolvedValue([]);

    afficher();
    await userEvent.type(screen.getByRole("searchbox"), "zzzz");

    expect(await screen.findByText(/aucun coureur/i)).toBeInTheDocument();
  });
});
