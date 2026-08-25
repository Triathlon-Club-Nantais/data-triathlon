import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act, within } from "@testing-library/react";
import type { Participation } from "@/lib/types";

let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const getAthlete = vi.fn();
vi.mock("@/lib/api/client", async () => {
  // `ApiError` reste la vraie classe (le composant fait `instanceof`, #502
  // item 11) — seul `apiClient.getAthlete` est simulé.
  const reel = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...reel,
    apiClient: { getAthlete: (...args: unknown[]) => getAthlete(...args) },
  };
});

import { ApiError } from "@/lib/api/client";
import { readAthlete, writeAthlete } from "@/components/layout/AthletePicker";
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

  it("refetch quand federalOnly change", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    await waitFor(() => expect(getAthlete).toHaveBeenCalledTimes(1));

    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={false} />);

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

  // #502, revue UI/UX item 1 : le rang a quitté la ligne principale (471px en
  // Anton 20px, ne tenait sur une ligne qu'au-delà de ~814px de viewport) pour
  // ouvrir la ligne secondaire, capitalisé — `all` s'y dit « meilleur
  // classement », ce qu'il est réellement.
  it("ouvre la ligne secondaire par le rang, capitalisé, `all` compris", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 2 })],
    });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    const ligneVisible = await screen.findByTestId("ma-saison-ligne");
    expect(within(ligneVisible).getByText(/^Classement général ·/)).toBeInTheDocument();
    // La ligne principale ne porte plus le parenthétique.
    expect(within(ligneVisible).queryByText(/\(classement général\)/)).not.toBeInTheDocument();

    searchParams = new URLSearchParams("rank=all");
    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(
      await within(ligneVisible).findByText(/^Meilleur classement ·/),
    ).toBeInTheDocument();
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

  // #502, item 7 : `AnnonceStatut` est déjà monté dans les quatre branches —
  // seul `busy` restait sans porteur pendant l'attente, laissant un aller-
  // retour muet côté auditif en plus du visuel (squelette #d6d1c8 à 1,52:1,
  // hors périmètre de ce lot — `components/ui/skeleton.tsx`).
  it("porte `aria-busy` sur la région d'annonce pendant le chargement", () => {
    getAthlete.mockReturnValue(new Promise(() => {}));
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  // #502, item 4 : même destination `/ajouter` nommée « Ajouter une épreuve »
  // partout ailleurs sur l'écran (`dashboard/page.tsx`, le rail) —
  // « résultat » n'est le mot d'aucun autre appelant.
  it("propose une sortie quand ma saison est vide", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    const ligneVisible = await screen.findByTestId("ma-saison-ligne");
    expect(within(ligneVisible).getByText(/aucune épreuve/i)).toBeInTheDocument();
    expect(
      within(ligneVisible).getByRole("link", { name: /ajouter une épreuve/i }),
    ).toHaveAttribute("href", "/ajouter");
  });

  describe("échec réseau (#502, item 5)", () => {
    it("garde le nom et le lien, et propose Réessayer", async () => {
      getAthlete.mockRejectedValue(new TypeError("Failed to fetch"));
      render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

      expect(await screen.findByText(/chiffres indisponibles/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /mon athlète/i })).toHaveAttribute(
        "href",
        "/athletes/12",
      );
      expect(getAthlete).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: /réessayer/i })).toBeInTheDocument();
    });

    it("« Réessayer » rejoue le fetch", async () => {
      getAthlete.mockRejectedValue(new TypeError("Failed to fetch"));
      render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
      await screen.findByRole("button", { name: /réessayer/i });
      expect(getAthlete).toHaveBeenCalledTimes(1);

      getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [ligne(1)] });
      await act(async () => {
        screen.getByRole("button", { name: /réessayer/i }).click();
      });

      await waitFor(() => expect(getAthlete).toHaveBeenCalledTimes(2));
      expect(await screen.findByTestId("ma-saison-ligne")).toBeInTheDocument();
    });

    // Ne jamais purger le stock sur une panne réseau (item 11) : ce serait
    // perdre le choix de quelqu'un dont l'athlète existe très bien.
    it("ne purge pas le stock sur une panne réseau", async () => {
      getAthlete.mockRejectedValue(new TypeError("Failed to fetch"));
      render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

      await screen.findByText(/chiffres indisponibles/i);
      expect(readAthlete()).toEqual(ATHLETE);
    });
  });

  // #502, revue UI/UX item 11 (décision de l'utilisateur) : un 404 signe une
  // fiche disparue (suppression, fusion admin) — la bande purge le stock et
  // invite un nouveau choix, au lieu de rester bloquée sur un profil mort.
  describe("athlète disparu — 404 (#502, item 11)", () => {
    it("purge le stock et invite à choisir un nom à nouveau", async () => {
      getAthlete.mockRejectedValue(new ApiError(404, "Not Found"));
      render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

      expect(await screen.findByText(/votre fiche a changé/i)).toBeInTheDocument();
      expect(screen.getByText(/choisissez votre nom à nouveau/i)).toBeInTheDocument();
      expect(readAthlete()).toBeNull();
      // La bande reste montée à la même hauteur réservée, sous le même
      // Eyebrow — jamais démontée, sans quoi rien ne relierait le message au
      // geste de sélection qui l'a précédé. (Deux nœuds portent le texte :
      // l'`Eyebrow` visible et le `h2` masqué du titre, item 6.)
      expect(screen.getAllByText("Ma saison").length).toBeGreaterThan(0);
    });

    it("ne montre ni « chiffres indisponibles » ni le lien de profil mort", async () => {
      getAthlete.mockRejectedValue(new ApiError(404, "Not Found"));
      render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

      await screen.findByText(/votre fiche a changé/i);
      expect(screen.queryByText(/chiffres indisponibles/i)).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /mon athlète/i })).not.toBeInTheDocument();
    });

    it("le bouton d'invitation ouvre la palette (OPEN_PICKER_EVENT)", async () => {
      getAthlete.mockRejectedValue(new ApiError(404, "Not Found"));
      render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

      const bouton = await screen.findByRole("button", { name: /choisir mon athlète/i });
      const ecouteur = vi.fn();
      window.addEventListener("tcn-athlete-open-picker", ecouteur);

      await act(async () => {
        bouton.click();
      });

      expect(ecouteur).toHaveBeenCalledTimes(1);
    });
  });
});

// #502, revue UI/UX item 6 (WCAG 1.3.1) : `Eyebrow` rend un `<div>`, invisible
// à un parcours par titres — le `h2` masqué relaie son texte pour que la
// bande soit atteignable comme ses deux voisins immédiats (`dashboard/
// page.tsx`, `RecentCourses.tsx`), tous deux des `h2`.
describe("MaSaison — titre accessible (#502, item 6)", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("expose un h2 masqué repris de l'Eyebrow visible", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    await screen.findByTestId("ma-saison-ligne");
    expect(screen.getByRole("heading", { level: 2, name: "Ma saison" })).toBeInTheDocument();
  });
});

// #502, revue UI/UX item 10 : « Ma saison » présuppose une saison unique — faux
// dès que `SeasonSelector` en retient plusieurs, où le h1 juste au-dessus dit
// « N saisons sélectionnées » (`lib/utils/season.ts`).
describe("MaSaison — titre au pluriel sur sélection multi-saisons (#502, item 10)", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("reste « Ma saison » sur une saison unique", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    await screen.findByTestId("ma-saison-ligne");
    expect(screen.getByRole("heading", { level: 2, name: "Ma saison" })).toBeInTheDocument();
  });

  it("devient « Mes saisons » sur une sélection multiple", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    render(<MaSaison clubEvents={32} seasons="2026,2025" federalOnly={true} />);

    await screen.findByTestId("ma-saison-ligne");
    expect(screen.getByRole("heading", { level: 2, name: "Mes saisons" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "Ma saison" })).not.toBeInTheDocument();
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

    // Le nœud existe dès la première peinture (montage inconditionnel) : seul
    // son texte reste vide tant qu'aucun changement n'a eu lieu.
    expect(screen.getByRole("status")).toHaveTextContent("");
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
    expect(screen.getByRole("status")).toHaveTextContent("");

    searchParams = new URLSearchParams("rank=category");
    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/1 podium/),
    );
  });

  it("annonce le nouveau résumé après un changement de saison", async () => {
    getAthlete.mockResolvedValueOnce({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 2 })],
    });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    await screen.findByTestId("ma-saison-ligne");
    expect(screen.getByRole("status")).toHaveTextContent("");

    getAthlete.mockResolvedValueOnce({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 2 }), ligne(2, { rank_overall: 5 })],
    });
    rerender(<MaSaison clubEvents={32} seasons="2024" federalOnly={true} />);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/2 épreuves/),
    );
  });
});
