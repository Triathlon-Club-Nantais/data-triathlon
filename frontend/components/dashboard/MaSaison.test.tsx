import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act, within } from "@testing-library/react";
import type { Participation } from "@/lib/types";

let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const getAthlete = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: { getAthlete: (...args: unknown[]) => getAthlete(...args) },
}));

import { writeAthlete } from "@/components/layout/AthletePicker";
import { MaSaison } from "./MaSaison";

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont" };

function ligne(courseId: number, rangs: Partial<Participation> = {}): Participation {
  return {
    course: { id: courseId },
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    is_pending_validation: false,
    ...rangs,
  } as unknown as Participation;
}

beforeEach(() => {
  searchParams = new URLSearchParams();
  getAthlete.mockReset();
  const stock = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (cle: string) => stock.get(cle) ?? null,
      setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
      removeItem: (cle: string) => void stock.delete(cle),
      clear: () => stock.clear(),
    },
  });
});

describe("MaSaison — état « aucun athlète retenu »", () => {
  it("ne rend rien et n'appelle pas l'API", () => {
    const { container } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(getAthlete).not.toHaveBeenCalled();
  });
});

describe("MaSaison — état rempli", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("met mes épreuves et mes podiums en regard du club", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [
        ligne(1, { rank_overall: 2 }),
        ligne(2, { rank_overall: 40 }),
        ligne(3, { rank_overall: 18 }),
        ligne(4, { rank_overall: 7 }),
      ],
    });

    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    // Portée sur la ligne visible : la région d'annonce (#477) reprend le
    // même texte en sr-only dès qu'elle s'affiche, ce qui recoupe une requête
    // non scopée (patron de `StatCardsRank.test.tsx`).
    const ligneVisible = await screen.findByTestId("ma-saison-ligne");
    expect(within(ligneVisible).getByText(/4 épreuves/)).toBeInTheDocument();
    expect(within(ligneVisible).getByText(/1 podium/)).toBeInTheDocument();
    expect(within(ligneVisible).getByText(/32/)).toBeInTheDocument();
  });

  it("transmet les filtres du tableau de bord à l'API", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });

    render(<MaSaison clubEvents={32} seasons="2025,2024" federalOnly={true} />);

    await waitFor(() =>
      expect(getAthlete).toHaveBeenCalledWith(12, {
        seasons: "2025,2024",
        federal_only: true,
      }),
    );
  });

  it("refetch quand la sélection de saisons change", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    await waitFor(() => expect(getAthlete).toHaveBeenCalledTimes(1));

    rerender(<MaSaison clubEvents={12} seasons="2024" federalOnly={true} />);

    await waitFor(() => expect(getAthlete).toHaveBeenCalledTimes(2));
  });

  // Même arbitrage que RankTypeToggle (#328) : le mode de rang ne change que
  // la lecture d'un champ déjà en main.
  it("ne refetch pas au changement de ?rank=, mais recompte le podium", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 40, rank_category: 2 })],
    });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    const ligneVisible = await screen.findByTestId("ma-saison-ligne");
    expect(within(ligneVisible).getByText(/0 podium/)).toBeInTheDocument();

    searchParams = new URLSearchParams("rank=category");
    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await within(ligneVisible).findByText(/1 podium/)).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledTimes(1);
  });

  it("apparaît quand l'athlète est choisi en cours de page", async () => {
    window.localStorage.removeItem("tcn-athlete");
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [ligne(1)] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    expect(getAthlete).not.toHaveBeenCalled();

    act(() => writeAthlete(ATHLETE));

    const ligneVisible = await screen.findByTestId("ma-saison-ligne");
    expect(within(ligneVisible).getByText(/1 épreuve/)).toBeInTheDocument();
  });
});

describe("MaSaison — états dégradés", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("affiche un squelette pendant le chargement", () => {
    getAthlete.mockReturnValue(new Promise(() => {}));
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    expect(screen.getByTestId("ma-saison-squelette")).toBeInTheDocument();
  });

  it("propose une sortie quand ma saison est vide", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    const ligneVisible = await screen.findByTestId("ma-saison-ligne");
    expect(within(ligneVisible).getByText(/aucune épreuve/i)).toBeInTheDocument();
    expect(
      within(ligneVisible).getByRole("link", { name: /ajouter un résultat/i }),
    ).toHaveAttribute("href", "/ajouter");
  });

  it("garde le nom et le lien quand le fetch échoue", async () => {
    getAthlete.mockRejectedValue(new Error("réseau"));
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await screen.findByText(/chiffres indisponibles/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /mon athlète/i })).toHaveAttribute(
      "href",
      "/athletes/12",
    );
  });
});

// WCAG 4.1.3 (#477) : `?rank=` ne navigue pas (`history.pushState`, #328),
// donc rien n'annonce la bascule à un lecteur d'écran sans cette région. Muette
// à la première apparition, pour ne pas transformer chaque chargement de page
// en bruit — patron vérifié séparément de la ligne visible, comme
// `StatCardsRank.test.tsx` (`getByRole("status")`, pas une requête de texte
// partagée avec le contenu visible).
describe("MaSaison — annonce (#477)", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("reste silencieuse à la première apparition", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 2 })],
    });

    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    await screen.findByTestId("ma-saison-ligne");

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("annonce le nouveau résumé après un changement de ?rank=", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 40, rank_category: 2 })],
    });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    await screen.findByTestId("ma-saison-ligne");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    searchParams = new URLSearchParams("rank=category");
    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/1 podium/),
    );
  });
});
