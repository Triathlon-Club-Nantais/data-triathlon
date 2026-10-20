import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AthleteSeasonActivity } from "@/lib/types";
import { writeAthlete } from "@/components/layout/AthletePicker";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/club/athletes",
  useSearchParams: () => searchParams,
}));

import { AthleteSeasonList } from "./AthleteSeasonList";

function athlete(over: Partial<AthleteSeasonActivity> & { id: number }): AthleteSeasonActivity {
  const participation_count = over.participation_count ?? 1;
  return {
    nom: "NOM",
    prenom: "Prénom",
    gender: "",
    participation_count,
    total_count: participation_count,
    validated_count: participation_count,
    club_affiliated_count: participation_count,
    season_validated: null,
    quota_met: null,
    ...over,
  };
}

function rowNames(): string[] {
  return screen.getAllByTestId("athlete-row-nom").map((el) => el.textContent);
}

describe("AthleteSeasonList", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
  });

  it("rend une ligne par athlète avec son nom complet et son compteur d'épreuves", () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "DUPONT", prenom: "Jean", participation_count: 3 }),
          athlete({ id: 2, nom: "MARTIN", prenom: "Julie", participation_count: 1 }),
        ]}
      />,
    );

    expect(screen.getByText("DUPONT")).toBeInTheDocument();
    expect(screen.getByText("Jean")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("MARTIN")).toBeInTheDocument();
  });

  it("#709 : affiche le total réel en compteur principal, distinct des validées/affiliées club", () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({
            id: 1,
            nom: "SOUSCOMPTE",
            total_count: 5,
            validated_count: 4,
            club_affiliated_count: 3,
          }),
        ]}
      />,
    );

    expect(screen.getByTestId("athlete-row-total")).toHaveTextContent("5");
    expect(screen.getByTestId("athlete-row-detail")).toHaveTextContent(/4 validée/i);
    expect(screen.getByTestId("athlete-row-detail")).toHaveTextContent(/3 affiliée/i);
  });

  it("#709 : n'affiche pas de détail redondant quand les trois compteurs sont identiques", () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "COMPLET", total_count: 2, validated_count: 2, club_affiliated_count: 2 }),
        ]}
      />,
    );

    expect(screen.queryByTestId("athlete-row-detail")).not.toBeInTheDocument();
  });

  it("#709 : affiche un badge « Saison validée » quand season_validated est vrai (saison unique)", () => {
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 1, nom: "VALIDE", season_validated: true })]}
      />,
    );

    expect(screen.getByText(/saison validée/i)).toBeInTheDocument();
  });

  it("#1402 : le badge « Saison validée » est écrit en orange profond (contraste AA), pas en orange de marque", () => {
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 1, nom: "VALIDE", season_validated: true })]}
      />,
    );

    const badge = screen.getByText(/saison validée/i);
    expect(badge.style.color).toBe("var(--tcn-orange-deeper)");
  });

  it("#709 : n'affiche aucun badge de validation quand plusieurs saisons sont sélectionnées (season_validated null)", () => {
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 1, nom: "MULTI", season_validated: null })]}
      />,
    );

    expect(screen.queryByText(/saison validée/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: /statut de validation/i })).not.toBeInTheDocument();
  });

  it("#709 : filtre par statut de validation quand la saison est unique (FR-014)", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "VALIDE", season_validated: true }),
          athlete({ id: 2, nom: "NONVALIDE", season_validated: false }),
        ]}
      />,
    );

    await userEvent.click(screen.getByRole("radio", { name: /^validées$/i }));

    expect(rowNames()).toEqual(["VALIDE"]);
  });

  it("#1542 : « Quota atteint, à valider » ne garde que les quotas atteints non validés", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "AVALIDER", season_validated: false, quota_met: true }),
          athlete({ id: 2, nom: "DEJAVALIDE", season_validated: true, quota_met: true }),
          athlete({ id: 3, nom: "INCOMPLET", season_validated: false, quota_met: false }),
        ]}
      />,
    );

    await userEvent.click(screen.getByRole("radio", { name: /quota atteint, à valider/i }));

    expect(rowNames()).toEqual(["AVALIDER"]);
  });

  it("#1542 : pastille « Quota atteint » sur un athlète à valider, pas sur un validé ni un incomplet", () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "AVALIDER", season_validated: false, quota_met: true }),
          athlete({ id: 2, nom: "DEJAVALIDE", season_validated: true, quota_met: true }),
          athlete({ id: 3, nom: "INCOMPLET", season_validated: false, quota_met: false }),
        ]}
      />,
    );

    expect(screen.getAllByText(/^quota atteint$/i)).toHaveLength(1);
  });

  it("#1542 : un filtre de statut vide le dit, et « Afficher tous » rend la liste", async () => {
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 1, nom: "DEJAVALIDE", season_validated: true, quota_met: true })]}
      />,
    );

    await userEvent.click(screen.getByRole("radio", { name: /quota atteint, à valider/i }));

    expect(screen.getByText(/aucun athlète ne correspond à ce statut/i)).toBeInTheDocument();
    expect(screen.queryByText(/essayez un autre nom/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /afficher tous/i }));
    expect(rowNames()).toEqual(["DEJAVALIDE"]);
  });

  it("#1562 : une recherche qui trouve mais un statut qui vide accuse le statut, et « Afficher tous » garde la recherche", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "DUPONT", season_validated: true, quota_met: true }),
          athlete({ id: 2, nom: "MARTIN", season_validated: false, quota_met: false }),
        ]}
      />,
    );

    await userEvent.type(screen.getByRole("searchbox", { name: /rechercher un athlète/i }), "Dupont");
    await userEvent.click(screen.getByRole("radio", { name: /^non validées$/i }));

    expect(screen.getByText(/aucun athlète ne correspond à ce statut/i)).toBeInTheDocument();
    expect(screen.queryByText(/essayez un autre nom/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /afficher tous/i }));
    expect(rowNames()).toEqual(["DUPONT"]);
    expect(screen.getByRole("searchbox", { name: /rechercher un athlète/i })).toHaveValue("Dupont");
  });

  it("#1562 : une recherche qui ne trouve personne garde « Essayez un autre nom », même sous un statut", async () => {
    render(
      <AthleteSeasonList athletes={[athlete({ id: 1, nom: "DUPONT", season_validated: true, quota_met: true })]} />,
    );

    await userEvent.click(screen.getByRole("radio", { name: /^non validées$/i }));
    await userEvent.type(screen.getByRole("searchbox", { name: /rechercher un athlète/i }), "Zorro");

    expect(screen.getByText(/essayez un autre nom/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /afficher tous/i })).not.toBeInTheDocument();
  });

  it("#1542 : ni option de quota ni pastille sur plusieurs saisons (quota_met null)", () => {
    render(<AthleteSeasonList athletes={[athlete({ id: 1, nom: "MULTI" })]} />);

    expect(screen.queryByRole("radio", { name: /quota atteint/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/^quota atteint$/i)).not.toBeInTheDocument();
  });

  it("liste vide (FR-007) : affiche un état vide explicite qui invite à changer de saison", () => {
    // Revue UI/UX #274 — un état vide oriente vers une action, jamais
    // « Aucune donnée » nu.
    render(<AthleteSeasonList athletes={[]} />);

    expect(screen.getByText(/aucun athlète/i)).toBeInTheDocument();
    expect(screen.getByText(/essayez une autre saison/i)).toBeInTheDocument();
  });

  it("tri par défaut : nombre d'épreuves décroissant", () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "PEU", participation_count: 1 }),
          athlete({ id: 2, nom: "BEAUCOUP", participation_count: 5 }),
        ]}
      />,
    );

    expect(rowNames()).toEqual(["BEAUCOUP", "PEU"]);
  });

  it("égalité de compteur : départage par nom de famille (Edge Cases du spec)", () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "ZEBRE", participation_count: 2 }),
          athlete({ id: 2, nom: "ALPHA", participation_count: 2 }),
        ]}
      />,
    );

    expect(rowNames()).toEqual(["ALPHA", "ZEBRE"]);
  });

  it("nom vide (import mal renseigné) : fin de tri, pas de crash (Edge Cases du spec)", () => {
    searchParams = new URLSearchParams("sort=nom");
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "", prenom: "X", participation_count: 1 }),
          athlete({ id: 2, nom: "ALPHA", prenom: "A", participation_count: 1 }),
        ]}
      />,
    );

    expect(rowNames()).toEqual(["ALPHA", ""]);
  });

  it("?sort=nom → tri alphabétique par nom de famille, quel que soit le compteur", () => {
    searchParams = new URLSearchParams("sort=nom");
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "ZEBRE", participation_count: 9 }),
          athlete({ id: 2, nom: "ALPHA", participation_count: 1 }),
        ]}
      />,
    );

    expect(rowNames()).toEqual(["ALPHA", "ZEBRE"]);
  });

  it("champ de recherche (#382) : filtre par nom ou prénom au fil de la frappe", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "DUPONT", prenom: "Jean" }),
          athlete({ id: 2, nom: "MARTIN", prenom: "Julie" }),
        ]}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText(/rechercher un athlète/i), "dupont");

    expect(rowNames()).toEqual(["DUPONT"]);
  });

  it("recherche insensible à la casse et aux accents, et matche aussi le prénom (#382)", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "LEMÉE", prenom: "Éric" }),
          athlete({ id: 2, nom: "MARTIN", prenom: "Julie" }),
        ]}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText(/rechercher un athlète/i), "eric");

    expect(rowNames()).toEqual(["LEMÉE"]);
  });

  it("recherche « prénom nom » mot à mot, comme name_filter côté API (#357, #382)", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "DUPONT", prenom: "Jean" }),
          athlete({ id: 2, nom: "MARTIN", prenom: "Julie" }),
        ]}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText(/rechercher un athlète/i), "jean dupont");

    expect(rowNames()).toEqual(["DUPONT"]);
  });

  it("champ de recherche accessible : porte un aria-label (#382)", () => {
    render(<AthleteSeasonList athletes={[athlete({ id: 1 })]} />);

    expect(screen.getByRole("searchbox", { name: /rechercher un athlète/i })).toBeInTheDocument();
  });

  it("champ de recherche visible : porte une icône de recherche, comme AthletePicker (#652)", () => {
    render(<AthleteSeasonList athletes={[athlete({ id: 1 })]} />);

    expect(screen.getByText("⌕")).toBeInTheDocument();
  });

  it("aucun résultat de recherche : invite à réessayer, pas un constat nu (revue ui-ux #382)", async () => {
    render(<AthleteSeasonList athletes={[athlete({ id: 1, nom: "DUPONT" })]} />);

    await userEvent.type(screen.getByPlaceholderText(/rechercher un athlète/i), "zzz");

    expect(screen.getByText(/essayez un autre nom/i)).toBeInTheDocument();
  });

  it("le nombre de résultats est annoncé aux lecteurs d'écran (WCAG 4.1.3, #382)", async () => {
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "DUPONT" }),
          athlete({ id: 2, nom: "MARTIN" }),
        ]}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText(/rechercher un athlète/i), "dupont");

    expect(screen.getByRole("status")).toHaveTextContent(/1 athlète/i);
  });
});

describe("AthleteSeasonList — retrouver sa ligne (#504)", () => {
  const descripteurOriginal = Object.getOwnPropertyDescriptor(window, "localStorage")!;

  beforeEach(() => {
    searchParams = new URLSearchParams();
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

  afterEach(() => {
    Object.defineProperty(window, "localStorage", descripteurOriginal);
  });

  it("ne marque aucune ligne et n'affiche pas de rappel quand aucun athlète n'est retenu", () => {
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 1, nom: "DUPONT" }), athlete({ id: 2, nom: "MARTIN" })]}
      />,
    );

    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("marque ma ligne d'un chip et d'un fond, sans rappel, quand elle est dans les 12 premières", () => {
    writeAthlete({ id: 2, prenom: "Julie", nom: "MARTIN" });
    render(
      <AthleteSeasonList
        athletes={[
          athlete({ id: 1, nom: "DUPONT", participation_count: 5 }),
          athlete({ id: 2, nom: "MARTIN", participation_count: 3 }),
        ]}
      />,
    );

    const marque = screen.getByText("Vous");
    const ligne = marque.closest("a") as HTMLElement;
    expect(ligne).toHaveTextContent("MARTIN");
    expect(ligne.className).toMatch(/(^|\s)tcn-rowlink--moi(\s|$)/);
    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("chaque ligne porte un id d'ancre `athlete-{id}`", () => {
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 7, nom: "DUPONT" }), athlete({ id: 8, nom: "MARTIN" })]}
      />,
    );

    expect(document.getElementById("athlete-7")).toHaveTextContent("DUPONT");
    expect(document.getElementById("athlete-8")).toHaveTextContent("MARTIN");
  });

  it("affiche un rappel épinglé quand ma ligne est hors des 12 premières, avec mon rang et mon ancre", () => {
    // 13 athlètes triés par volume décroissant : celui d'id 99 (1 épreuve)
    // est 13e, hors du seuil de 12.
    const athletes = Array.from({ length: 12 }, (_, i) =>
      athlete({ id: i + 1, nom: `N${i}`, participation_count: 12 - i + 1 }),
    );
    athletes.push(athlete({ id: 99, nom: "MOI", participation_count: 1 }));
    writeAthlete({ id: 99, prenom: "M", nom: "MOI" });

    render(<AthleteSeasonList athletes={athletes} />);

    const rappel = screen.getByRole("link", { name: /Vous : 1 épreuve — 13ᵉ du club/ });
    expect(rappel).toHaveAttribute("href", "#athlete-99");
  });

  it("le rang du rappel se calcule sur la liste complète, pas sur le résultat filtré par la recherche", async () => {
    const athletes = Array.from({ length: 12 }, (_, i) =>
      athlete({ id: i + 1, nom: `N${i}`, participation_count: 12 - i + 1 }),
    );
    athletes.push(athlete({ id: 99, nom: "MOI", participation_count: 1 }));
    writeAthlete({ id: 99, prenom: "M", nom: "MOI" });

    render(<AthleteSeasonList athletes={athletes} />);
    await userEvent.type(screen.getByPlaceholderText(/rechercher un athlète/i), "N0");

    expect(screen.getByRole("link", { name: /13ᵉ du club/ })).toBeInTheDocument();
  });

  it("pas de rappel quand je suis exactement au seuil (12ᵉ, dans les 12 premières)", () => {
    const athletes = Array.from({ length: 12 }, (_, i) =>
      athlete({ id: i + 1, nom: `N${i}`, participation_count: 12 - i + 1 }),
    );
    writeAthlete({ id: 12, prenom: "M", nom: "N11" });

    render(<AthleteSeasonList athletes={athletes} />);

    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("aucun highlight ni rappel quand l'athlète retenu n'est pas dans cette saison", () => {
    writeAthlete({ id: 404, prenom: "Absent", nom: "DeSaison" });
    render(
      <AthleteSeasonList
        athletes={[athlete({ id: 1, nom: "DUPONT" }), athlete({ id: 2, nom: "MARTIN" })]}
      />,
    );

    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("le rang du rappel reste celui du volume, même quand l'écran est trié par nom (#504, revue)", () => {
    // Triée par nom, MOI (« AAA ») serait 1ère — mais « Rᵉ du club » promet
    // un rang de club, cohérent avec le rappel de /club (toujours trié par
    // volume, `club_roster`/`club_rank` côté backend) : basculer le tri
    // d'affichage ne doit pas changer ce que ce nombre veut dire.
    searchParams = new URLSearchParams("sort=nom");
    const athletes = Array.from({ length: 12 }, (_, i) =>
      athlete({ id: i + 1, nom: `N${i}`, participation_count: 12 - i + 1 }),
    );
    athletes.push(athlete({ id: 99, nom: "AAA", participation_count: 1 }));
    writeAthlete({ id: 99, prenom: "M", nom: "AAA" });

    render(<AthleteSeasonList athletes={athletes} />);

    expect(screen.getByRole("link", { name: /13ᵉ du club/ })).toBeInTheDocument();
  });

  describe("sexe", () => {
    const mixed = [
      athlete({ id: 1, nom: "HOMME", gender: "M" }),
      athlete({ id: 2, nom: "FEMME", gender: "F" }),
    ];

    it("filters the list by sexe=F", () => {
      searchParams = new URLSearchParams("sexe=F");
      render(<AthleteSeasonList athletes={mixed} />);
      expect(rowNames()).toEqual(["FEMME"]);
    });

    it("computes the recall rank among the filtered sex only", () => {
      writeAthlete({ id: 2, prenom: "P", nom: "FEMME" });
      searchParams = new URLSearchParams("sexe=F");
      const many = [
        ...Array.from({ length: 30 }, (_, i) => athlete({ id: 100 + i, nom: `H${i}`, gender: "M", participation_count: 50 - i })),
        athlete({ id: 2, nom: "FEMME", gender: "F", participation_count: 1 }),
      ];
      render(<AthleteSeasonList athletes={many} />);
      expect(screen.queryByText(/ᵉ du club/)).not.toBeInTheDocument();
    });

    it("names the sex and offers to drop it when nobody of that sex is active", () => {
      searchParams = new URLSearchParams("seasons=2025&sexe=F");
      render(<AthleteSeasonList athletes={[athlete({ id: 1, nom: "HOMME", gender: "M" })]} />);
      expect(screen.getByText("Aucun athlète actif chez les femmes sur cette saison.")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Voir tous les athlètes" })).toHaveAttribute(
        "href",
        "/club/athletes?seasons=2025",
      );
    });

    it("names the sex filter, not only the name, when the search misses that sex", async () => {
      searchParams = new URLSearchParams("sexe=F");
      render(<AthleteSeasonList athletes={mixed} />);
      await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un athlète" }), "homme");
      expect(
        screen.getByText("Aucun athlète ne correspond à « homme » chez les femmes."),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Voir tous les athlètes" })).toHaveAttribute("href", "/club/athletes");
    });

    it("qualifies the recall rank with the filtered sex and hides it for the other sex", () => {
      searchParams = new URLSearchParams("sexe=F");
      const many = [
        ...Array.from({ length: 12 }, (_, i) => athlete({ id: 100 + i, nom: `F${i}`, gender: "F", participation_count: 50 - i })),
        athlete({ id: 2, nom: "FEMME", gender: "F", participation_count: 1 }),
        athlete({ id: 3, nom: "HOMME", gender: "M", participation_count: 1 }),
      ];
      writeAthlete({ id: 2, prenom: "P", nom: "FEMME" });
      const { unmount } = render(<AthleteSeasonList athletes={many} />);
      expect(screen.getByRole("link", { name: /13ᵉ chez les femmes du club/ })).toBeInTheDocument();
      unmount();
      writeAthlete({ id: 3, prenom: "P", nom: "HOMME" });
      render(<AthleteSeasonList athletes={many} />);
      expect(screen.queryByText(/ᵉ .*du club/)).not.toBeInTheDocument();
    });

    it("renders a visible Sexe label next to the toggle", () => {
      render(<AthleteSeasonList athletes={mixed} />);
      expect(screen.getByText("Sexe")).toBeVisible();
    });

    it("renders the sexe toggle", () => {
      render(<AthleteSeasonList athletes={mixed} />);
      expect(screen.getByRole("group", { name: "Sexe" })).toBeInTheDocument();
    });

    it("shows everyone without sexe", () => {
      render(<AthleteSeasonList athletes={mixed} />);
      expect(rowNames().sort()).toEqual(["FEMME", "HOMME"]);
    });
  });
});
