import { describe, it, expect } from "vitest";
import { groupEventsByCompetition, eventSuffix } from "./eventGroups";
import type { EventOut } from "@/lib/types";

function ev(id: number, event_name: string, extra: Partial<EventOut> = {}): EventOut {
  return {
    id,
    event_name,
    event_date: "2026-06-13",
    event_type: "triathlon-s",
    is_relay: false,
    total: 10,
    tcn_count: 1,
    ...extra,
  };
}

const PREFIXE = "MEDOC ATLANTIQUE FRENCHMAN Triathlon Carcans 2026";

describe("groupEventsByCompetition", () => {
  it("réunit les épreuves contiguës partageant le préfixe avant le premier « - »", () => {
    const groupes = groupEventsByCompetition([
      ev(1, `${PREFIXE} - Frenchkid Aquathlon - 2013/2014 - Fille`),
      ev(2, `${PREFIXE} - Frenchkid Aquathlon - 2013/2014 - Garçon`),
      ev(3, `${PREFIXE} - Frenchman XL`),
    ]);

    expect(groupes).toHaveLength(1);
    expect(groupes[0].prefix).toBe(PREFIXE);
    expect(groupes[0].events.map((e) => e.id)).toEqual([1, 2, 3]);
  });

  it("laisse une épreuve isolée dans un groupe d'un seul membre", () => {
    const groupes = groupEventsByCompetition([ev(7, "Triathlon de Nantes")]);

    expect(groupes).toHaveLength(1);
    expect(groupes[0].prefix).toBe("Triathlon de Nantes");
    expect(groupes[0].events.map((e) => e.id)).toEqual([7]);
  });

  it("ne fusionne pas deux séries non contiguës du même préfixe", () => {
    // Le tri de la liste est la source de vérité : fusionner à distance
    // déplacerait des lignes hors de leur position triée.
    const groupes = groupEventsByCompetition([
      ev(1, `${PREFIXE} - A`),
      ev(2, "Triathlon de Nantes - Sprint"),
      ev(3, `${PREFIXE} - B`),
    ]);

    expect(groupes.map((g) => g.events.map((e) => e.id))).toEqual([[1], [2], [3]]);
  });

  it("additionne les résultats et les TCN du groupe", () => {
    const groupes = groupEventsByCompetition([
      ev(1, `${PREFIXE} - A`, { total: 120, tcn_count: 3 }),
      ev(2, `${PREFIXE} - B`, { total: 80, tcn_count: 0 }),
    ]);

    expect(groupes[0].total).toBe(200);
    expect(groupes[0].tcnCount).toBe(3);
  });

  it("rend une liste vide sur une liste vide", () => {
    expect(groupEventsByCompetition([])).toEqual([]);
  });
});

describe("eventSuffix", () => {
  it("rend la part distinctive après le préfixe", () => {
    expect(eventSuffix(`${PREFIXE} - Frenchkid Aquathlon - 2015 - Fille`, PREFIXE)).toBe(
      "Frenchkid Aquathlon - 2015 - Fille",
    );
  });

  it("rend le nom entier quand il se confond avec le préfixe", () => {
    expect(eventSuffix("Triathlon de Nantes", "Triathlon de Nantes")).toBe("Triathlon de Nantes");
  });
});
