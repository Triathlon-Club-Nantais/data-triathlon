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
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();
  });

  it("permet d'annuler le choix en attente", async () => {
    const onChoisir = vi.fn();
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={CIBLE} onChoisir={onChoisir} />);
    await userEvent.click(screen.getByRole("button", { name: /Annuler ce choix/ }));
    expect(onChoisir).toHaveBeenCalledWith(null);
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();
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

  it("annonce la recherche en cours au lecteur d'écran (#608)", async () => {
    let resolveRecherche: (value: AthleteBrief[]) => void;
    searchAthletesBenevole.mockReturnValue(
      new Promise<AthleteBrief[]>((resolve) => {
        resolveRecherche = resolve;
      }),
    );
    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Ker");

    // `role="status"` (aria-live="polite" implicite) : jusqu'ici seul le
    // voyant voyait « Recherche… », rien ne le signalait au lecteur d'écran.
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Recherche…"));

    resolveRecherche!([CIBLE]);
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("ignore les réponses en retard si une recherche plus récente a abouti", async () => {
    const other: AthleteBrief = { id: 3, nom: "DURAND", prenom: "Jean", gender: "M", club: "TCN" };
    let resolveFirst: (value: AthleteBrief[]) => void;
    let resolveSecond: (value: AthleteBrief[]) => void;

    const firstPromise = new Promise<AthleteBrief[]>((resolve) => {
      resolveFirst = resolve;
    });
    const secondPromise = new Promise<AthleteBrief[]>((resolve) => {
      resolveSecond = resolve;
    });

    searchAthletesBenevole
      .mockReturnValueOnce(firstPromise)
      .mockReturnValueOnce(secondPromise);

    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);
    const input = screen.getByLabelText(/Réattribuer/);

    // Première recherche (au moins 2 caractères)
    await userEvent.type(input, "Ke");
    // Deuxième recherche (on tape plus)
    await userEvent.type(input, "r");

    // Résoudre la deuxième recherche d'abord (la plus récente)
    resolveSecond!([CIBLE]);
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());

    // Puis résoudre la première recherche en retard
    resolveFirst!([other]);

    // La première réponse en retard ne doit pas remplacer la deuxième plus récente
    expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument();
    expect(screen.queryByText(/DURAND/)).not.toBeInTheDocument();
  });

  it("ignore une réponse stale quand le champ est effacé en-dessous de 2 caractères", async () => {
    let resolvePending: (value: AthleteBrief[]) => void;
    const pendingPromise = new Promise<AthleteBrief[]>((resolve) => {
      resolvePending = resolve;
    });

    // Chaque appel à searchAthletesBenevole retourne la même Promise (qui ne sera jamais résolue jusqu'à nos appels)
    searchAthletesBenevole.mockReturnValue(pendingPromise);

    render(<ReattributionField athleteActuel={ACTUEL} athleteCible={null} onChoisir={vi.fn()} />);
    const input = screen.getByLabelText(/Réattribuer/);

    // Lancer une recherche (3 caractères = OK pour déclencher)
    await userEvent.type(input, "Ker");
    // Vérifier qu'on est en train de chercher
    await waitFor(() => expect(screen.getByText(/Recherche…/)).toBeInTheDocument());

    // Effacer pour revenir en-dessous de 2 caractères
    await userEvent.clear(input);

    // À ce stade, le champ est vide et les résultats ont été clearés
    expect(screen.queryByText(/Recherche…/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Aucun coureur trouvé/)).not.toBeInTheDocument();

    // Résoudre la réponse stale (celle en vol depuis "Ker")
    resolvePending!([CIBLE]);

    // L'état doit rester vide — la réponse stale ne doit pas s'afficher
    expect(screen.queryByText(/Hadrien KERMARREC/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Recherche…/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Recherche impossible/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Aucun coureur trouvé/)).not.toBeInTheDocument();
  });
});
