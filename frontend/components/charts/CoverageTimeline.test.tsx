import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoverageTimeline } from "./CoverageTimeline";

describe("CoverageTimeline", () => {
  it("affiche un état vide quand aucune donnée de couverture", () => {
    render(<CoverageTimeline months={[]} />);
    expect(screen.getByText("Pas encore de données de couverture.")).toBeInTheDocument();
  });

  it("n'affiche jamais l'année quand l'historique tient dans une seule année civile", () => {
    const months = [
      { month: "2026-01", count: 3 },
      { month: "2026-02", count: 0 },
      { month: "2026-03", count: 5 },
    ];
    const { container } = render(<CoverageTimeline months={months} />);
    const labels = [...container.querySelectorAll(".micro-label")].map((l) => l.textContent);
    expect(labels).toEqual(["janv", "févr", "mars"]);
  });

  it("affiche l'année sur le premier mois et au changement d'année quand l'historique dépasse un an (#700)", () => {
    // Régression : deux barres distinctes (ex. janvier 2025 et janvier 2026)
    // portaient le même libellé « janv » sans distinction dès que l'historique
    // du club dépassait une année civile.
    const months = [
      { month: "2025-11", count: 1 },
      { month: "2025-12", count: 0 },
      { month: "2026-01", count: 2 },
      { month: "2026-02", count: 4 },
    ];
    const { container } = render(<CoverageTimeline months={months} />);
    const labels = [...container.querySelectorAll(".micro-label")].map((l) => l.textContent);
    expect(labels).toEqual(["nov 2025", "déc", "janv 2026", "févr"]);
  });

  it("porte l'année dans le résumé accessible quand l'historique dépasse un an", () => {
    const months = [
      { month: "2025-12", count: 1 },
      { month: "2026-01", count: 2 },
    ];
    render(<CoverageTimeline months={months} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Couverture mensuelle des épreuves : déc 2025 1, janv 2026 2.",
    );
  });
});
