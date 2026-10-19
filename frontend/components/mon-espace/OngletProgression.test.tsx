import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Participation } from "@/lib/types";
import { OngletProgression } from "./OngletProgression";

let numero = 0;
function resultat(date: string, rank: number, extra: Record<string, unknown> = {}): Participation {
  numero += 1;
  return {
    id: numero,
    course: { id: numero, name: `E${numero}`, event_date: date, event_type: "triathlon-m", is_reliable: true, ...extra },
    rank_overall: rank, course_finishers: 100, is_pending_validation: false,
  } as unknown as Participation;
}

const courant = [resultat("2026-01-10", 40), resultat("2026-03-10", 25), resultat("2026-05-10", 10)];
const precedent = [resultat("2025-01-10", 50), resultat("2025-03-10", 45), resultat("2025-05-10", 30)];

describe("OngletProgression", () => {
  it("draws the current curve solid and the previous season dashed, both named in the summary", () => {
    const { container } = render(<OngletProgression courant={courant} precedent={precedent} seasons={[2025]} />);

    const chemins = container.querySelectorAll("svg path");
    expect(chemins).toHaveLength(2);
    expect(chemins[0]).not.toHaveAttribute("stroke-dasharray");
    expect(chemins[1]).toHaveAttribute("stroke-dasharray");
    const resume = screen.getByRole("img", { name: /Évolution du classement/ }).getAttribute("aria-label")!;
    expect(resume).toContain("Saison précédente");
    expect(resume).toContain("Cette saison");
  });

  it("leaves unreliable races out of the curve and mentions them", () => {
    const fiable = [...courant, resultat("2026-06-10", 5, { is_reliable: false })];
    const { container } = render(<OngletProgression courant={fiable} precedent={null} seasons={[2025]} />);

    expect(container.querySelectorAll("[data-point]")).toHaveLength(3);
    expect(container.querySelectorAll("svg path")).toHaveLength(1);
    expect(screen.getByText(/1 épreuve non fiable absente/)).toBeInTheDocument();
  });

  it("counts the unreliable races of both seasons, in the summary too", () => {
    const prec = [...precedent, resultat("2025-06-10", 5, { is_reliable: false })];
    const fiable = [...courant, resultat("2026-06-10", 5, { is_reliable: false })];
    render(<OngletProgression courant={fiable} precedent={prec} seasons={[2025]} />);

    expect(screen.getByText(/2 épreuves non fiables absentes/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Évolution du classement/ }).getAttribute("aria-label")).toContain("2 épreuves non fiables absentes");
  });

  it("hides the legend while the current curve is not drawn", () => {
    render(<OngletProgression courant={courant.slice(0, 2)} precedent={precedent} seasons={[2025]} />);

    expect(screen.queryByText(/Trait plein/)).toBeNull();
  });

  it("counts my races per month in the histogram", () => {
    render(<OngletProgression courant={[...courant, resultat("2026-03-20", 12)]} precedent={null} seasons={[2025]} />);

    expect(screen.getByRole("img", { name: /Mes épreuves par mois.*mars : 2/ })).toBeInTheDocument();
  });
});
