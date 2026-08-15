import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MonthlyTrend } from "./MonthlyTrend";

describe("MonthlyTrend", () => {
  it("affiche un état vide quand aucune donnée mensuelle", () => {
    render(<MonthlyTrend byMonth={{}} />);
    expect(screen.getByText("Pas encore de données mensuelles.")).toBeInTheDocument();
  });

  it("garde une hauteur minimale visible même à zéro résultat", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 0, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    expect(bars[0].style.height).toBe("4%");
  });

  it("donne 100% de hauteur au mois du maximum", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 0, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    expect(bars[1].style.height).toBe("100%");
  });

  it("ne garde que les 12 derniers mois, triés chronologiquement", () => {
    // 14 mois valides à cheval sur deux années : les clés `YYYY-MM` restent
    // triables lexicographiquement dans le bon ordre chronologique.
    const byMonth = {
      "2025-01": 1, "2025-02": 2, "2025-03": 3, "2025-04": 4,
      "2025-05": 5, "2025-06": 6, "2025-07": 7, "2025-08": 8,
      "2025-09": 9, "2025-10": 10, "2025-11": 11, "2025-12": 12,
      "2026-01": 13, "2026-02": 14,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const bars = [...container.querySelectorAll(".rounded-t-sm")];
    expect(bars.length).toBe(12);
  });
});
