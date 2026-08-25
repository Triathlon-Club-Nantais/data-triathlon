import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClubBreakdown } from "./ClubBreakdown";

const TROIS = [
  { name: "GRAVELINES TRIATHLON", count: 51, is_tcn: false },
  { name: "TRIATHLON CLUB NANTAIS", count: 4, is_tcn: true },
  { name: "ASPTT NANTES", count: 2, is_tcn: false },
];

describe("ClubBreakdown", () => {
  it("rend une ligne par club, du plus représenté au moins", () => {
    render(<ClubBreakdown clubs={TROIS} total={3} />);

    expect(screen.getByText("GRAVELINES TRIATHLON")).toBeInTheDocument();
    expect(screen.getByText("ASPTT NANTES")).toBeInTheDocument();
  });

  it("écrit le club TCN dans le seul token qui tient 4,5:1 (A11Y-4)", () => {
    render(<ClubBreakdown clubs={TROIS} total={3} />);

    expect(screen.getByText("TRIATHLON CLUB NANTAIS").style.color).toBe(
      "var(--tcn-orange-deeper)",
    );
  });

  // ── Ce que la carte omet (#486, RES-7) ─────────────────────────────────────

  it("compte les clubs non listés quand la liste est tronquée", () => {
    // Cas réel de la course 8 : 174 clubs distincts, neuf affichés.
    render(<ClubBreakdown clubs={TROIS} total={174} />);

    expect(screen.getByText("et 171 autres clubs")).toBeInTheDocument();
  });

  it("accorde le pied au singulier", () => {
    render(<ClubBreakdown clubs={TROIS} total={4} />);

    expect(screen.getByText("et 1 autre club")).toBeInTheDocument();
  });

  it("ne dit rien quand la liste est exhaustive", () => {
    render(<ClubBreakdown clubs={TROIS} total={3} />);

    expect(screen.queryByText(/autres? clubs?/)).not.toBeInTheDocument();
  });

  it("garde l'en-tête de colonnes quand aucun club n'est renseigné (#481)", () => {
    // Cas réel de la course 47 : 696 lignes, aucun club — l'en-tête reste,
    // l'état vide se rend après le tableau, jamais à sa place (A11Y-3).
    render(<ClubBreakdown clubs={[]} total={0} />);

    expect(screen.getByRole("columnheader", { name: "Club" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Athlètes" })).toBeInTheDocument();
    expect(screen.getByText("Clubs non renseignés")).toBeInTheDocument();
  });

  it("dit ce qu'il omet en texte, donc à un lecteur d'écran comme à l'œil", () => {
    // Le pied est du texte visible — donc déjà dans l'arbre d'accessibilité,
    // sans `aria-*` à ajouter.
    render(<ClubBreakdown clubs={TROIS} total={174} />);

    const pied = screen.getByText("et 171 autres clubs");
    expect(pied).toBeVisible();
    expect(pied).not.toHaveAttribute("aria-hidden");
  });
});
