import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AthleteSeasonActivity } from "@/lib/types";

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
});
