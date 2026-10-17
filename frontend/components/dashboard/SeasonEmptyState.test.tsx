import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeasonEmptyState } from "./SeasonEmptyState";
import { currentSeason } from "@/lib/utils/season";

describe("SeasonEmptyState (#1409)", () => {
  it("names the season and offers both exits with touch targets", () => {
    render(<SeasonEmptyState seasons={[2015]} currentSeasonHref="/mon-espace?scope=club" />);

    expect(screen.getByText("Aucun résultat enregistré pour la saison 2015 — 2016")).toBeInTheDocument();
    expect(screen.getByText("Changez de saison ou ajoutez les premiers résultats du club.")).toBeInTheDocument();
    const voir = screen.getByRole("link", { name: "Voir la saison en cours" });
    expect(voir).toHaveAttribute("href", "/mon-espace?scope=club");
    expect(voir).toHaveClass("tcn-cible-tactile");
    const ajouter = screen.getByRole("link", { name: "Ajouter une épreuve" });
    expect(ajouter).toHaveAttribute("href", "/ajouter");
    expect(ajouter).toHaveClass("tcn-cible-tactile");
    expect(ajouter.querySelector('[aria-hidden="true"]')).toHaveTextContent("→");
  });

  it("hides the current season exit when only the current season is shown", () => {
    render(<SeasonEmptyState seasons={[currentSeason()]} currentSeasonHref="/mon-espace" />);
    expect(screen.queryByRole("link", { name: "Voir la saison en cours" })).not.toBeInTheDocument();
  });

  it("treats an empty selection as the current season", () => {
    render(<SeasonEmptyState seasons={[]} currentSeasonHref="/resultats" />);
    expect(screen.queryByRole("link", { name: "Voir la saison en cours" })).not.toBeInTheDocument();
  });
});
