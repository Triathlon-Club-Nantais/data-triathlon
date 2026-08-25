import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
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

    expect(await screen.findByText(/4 épreuves/)).toBeInTheDocument();
    expect(screen.getByText(/1 podium/)).toBeInTheDocument();
    expect(screen.getByText(/32/)).toBeInTheDocument();
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
    expect(await screen.findByText(/0 podium/)).toBeInTheDocument();

    searchParams = new URLSearchParams("rank=category");
    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await screen.findByText(/1 podium/)).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledTimes(1);
  });

  it("apparaît quand l'athlète est choisi en cours de page", async () => {
    window.localStorage.removeItem("tcn-athlete");
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [ligne(1)] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    expect(getAthlete).not.toHaveBeenCalled();

    act(() => writeAthlete(ATHLETE));

    expect(await screen.findByText(/1 épreuve/)).toBeInTheDocument();
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

    expect(await screen.findByText(/aucune épreuve/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ajouter un résultat/i })).toHaveAttribute(
      "href",
      "/ajouter",
    );
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
