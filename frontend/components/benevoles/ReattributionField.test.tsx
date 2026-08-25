import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief } from "@/lib/types";

const { searchAthletesBenevole, reassignParticipationBenevole } = vi.hoisted(() => ({
  searchAthletesBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { searchAthletesBenevole, reassignParticipationBenevole } };
});

import { ReattributionField } from "./ReattributionField";

const ACTUEL: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const CIBLE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ReattributionField", () => {
  it("choisit un athlète sans rien écrire côté serveur", async () => {
    const onChoisir = vi.fn();
    searchAthletesBenevole.mockResolvedValue([CIBLE]);
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={onChoisir} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));

    expect(onChoisir).toHaveBeenCalledWith(CIBLE);
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();
  });

  it("annonce le choix en attente à côté de l'athlète d'origine", () => {
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={CIBLE} onChoisir={vi.fn()} />);
    expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument();
    expect(screen.getByText(/Mathieu HERRMANN/)).toBeInTheDocument();
  });

  it("permet d'annuler le choix en attente", async () => {
    const onChoisir = vi.fn();
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={CIBLE} onChoisir={onChoisir} />);
    await userEvent.click(screen.getByRole("button", { name: /Annuler ce choix/ }));
    expect(onChoisir).toHaveBeenCalledWith(null);
  });

  it("distingue une recherche en échec d'une recherche sans résultat", async () => {
    searchAthletesBenevole.mockRejectedValue(new Error("réseau"));
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");

    await waitFor(() =>
      expect(screen.getByText(/Recherche impossible pour le moment/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Aucun coureur trouvé/)).not.toBeInTheDocument();
  });

  it("affiche un état vide quand la recherche ne trouve personne", async () => {
    searchAthletesBenevole.mockResolvedValue([]);
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Zzz");

    await waitFor(() => expect(screen.getByText(/Aucun coureur trouvé/)).toBeInTheDocument());
  });
});
