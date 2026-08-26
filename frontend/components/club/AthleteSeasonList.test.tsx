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
  return { nom: "NOM", prenom: "Prénom", participation_count: 1, ...over };
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
    // volume, `buildRoster`) : basculer le tri d'affichage ne doit pas
    // changer ce que ce nombre veut dire.
    searchParams = new URLSearchParams("sort=nom");
    const athletes = Array.from({ length: 12 }, (_, i) =>
      athlete({ id: i + 1, nom: `N${i}`, participation_count: 12 - i + 1 }),
    );
    athletes.push(athlete({ id: 99, nom: "AAA", participation_count: 1 }));
    writeAthlete({ id: 99, prenom: "M", nom: "AAA" });

    render(<AthleteSeasonList athletes={athletes} />);

    expect(screen.getByRole("link", { name: /13ᵉ du club/ })).toBeInTheDocument();
  });
});
