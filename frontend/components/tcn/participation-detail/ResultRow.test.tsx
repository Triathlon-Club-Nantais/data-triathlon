import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";
import { ResultRow } from "./ResultRow";

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 42,
    athlete: { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: 3,
      name: "Triathlon de Nantes",
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "raceresult",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V1H",
    bib_number: "56",
    rank_overall: 56,
    rank_category: 4,
    rank_gender: 41,
    total_time: "02:02:31",
    status: "finisher",
    is_relay: false,
    splits: {
      swim: "00:22:52",
      t1: "00:02:55",
      bike: "01:01:07",
      t2: "00:01:54",
      run: "00:33:45",
    },
    created_at: null,
    ...over,
  };
}

const SEGMENTS = ["swim", "t1", "bike", "t2", "run"];

describe("ResultRow", () => {
  it("affiche l'identité, la catégorie, le sexe et le temps total", () => {
    render(<ResultRow participation={participation()} segments={SEGMENTS} />);

    expect(screen.getByText("DUPONT Jean")).toBeTruthy();
    expect(screen.getByText("V1H")).toBeTruthy();
    expect(screen.getByText("M")).toBeTruthy();
    expect(screen.getByText("02:02:31")).toBeTruthy();
  });

  it("affiche le rang scratch", () => {
    render(<ResultRow participation={participation()} segments={SEGMENTS} />);

    expect(screen.getByText("56")).toBeTruthy();
  });

  it("affiche chaque segment publié par l'épreuve", () => {
    const { container } = render(
      <ResultRow participation={participation()} segments={SEGMENTS} />,
    );

    const cells = container.querySelectorAll("[data-segment]");
    expect([...cells].map((c) => c.getAttribute("data-segment"))).toEqual(SEGMENTS);
  });

  it("rend un tiret pour un split absent, jamais un zéro", () => {
    const { container } = render(
      <ResultRow
        participation={participation({ splits: { swim: "00:22:52", bike: "01:01:07" } })}
        segments={SEGMENTS}
      />,
    );

    // Dernier enfant = la valeur du segment ; le premier porte son libellé.
    const valeur = container.querySelector('[data-segment="t1"]')?.lastElementChild;
    expect(valeur?.textContent).toBe("—");
    expect(valeur?.textContent).not.toMatch(/\d/);
  });

  it("distingue les transitions des disciplines chronométrées", () => {
    const { container } = render(
      <ResultRow participation={participation()} segments={SEGMENTS} />,
    );

    const transition = (key: string) =>
      container.querySelector(`[data-segment="${key}"]`)?.getAttribute("data-transition");

    expect(transition("t1")).toBe("true");
    expect(transition("t2")).toBe("true");
    expect(transition("swim")).toBe("false");
    expect(transition("bike")).toBe("false");
    expect(transition("run")).toBe("false");
  });

  it("n'ouvre pas de colonne pour un segment que l'épreuve ne publie pas", () => {
    const { container } = render(
      <ResultRow
        participation={participation({
          course: { ...participation().course, event_type: "duathlon-s" },
          splits: { course1: "00:15:00", bike: "00:40:00", course2: "00:18:00" },
        })}
        segments={["course1", "bike", "course2"]}
      />,
    );

    expect(container.querySelector('[data-segment="t1"]')).toBeNull();
    expect(container.querySelectorAll("[data-segment]").length).toBe(3);
  });
});
