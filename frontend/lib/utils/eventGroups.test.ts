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

  // #568, cas 1 : sous le tri « Nom », le backend rend deux éditions du même
  // nom adjacentes (`ORDER BY courses.name ASC, courses.event_date DESC`).
  // Elles partagent le préfixe mais pas la date : sans la date dans la clé,
  // elles fusionnaient sous une ligne unique qui affichait la date de la
  // seule première tout en sommant les compteurs des deux années.
  it("ne fusionne pas deux éditions du même nom à des dates différentes", () => {
    const groupes = groupEventsByCompetition([
      ev(1, "Triathlon de Mesquer", { event_date: "2026-05-16" }),
      ev(2, "Triathlon de Mesquer", { event_date: "2025-05-17" }),
    ]);

    expect(groupes).toHaveLength(2);
    expect(groupes.map((g) => g.events.map((e) => e.id))).toEqual([[1], [2]]);
  });

  // Non-régression #463 : des heats d'une même compétition, à la même date,
  // continuent de se replier sous une seule ligne — c'est le cas normal
  // (formats successifs d'un même week-end), la date seule ne doit rien
  // casser ici.
  it("regroupe toujours les heats d'une même compétition à la même date", () => {
    const groupes = groupEventsByCompetition([
      ev(1, `${PREFIXE} - Distance S`, { event_date: "2026-06-13" }),
      ev(2, `${PREFIXE} - Distance M`, { event_date: "2026-06-13" }),
    ]);

    expect(groupes).toHaveLength(1);
    expect(groupes[0].events.map((e) => e.id)).toEqual([1, 2]);
  });

  // `event_date` est une mise à vide légitime (`lib/types.ts`). Comportement
  // retenu : une épreuve non datée ne fusionne jamais avec une épreuve datée
  // du même préfixe (les dates diffèrent, `null !== "2026-05-16"`) ; deux
  // épreuves non datées du même préfixe se regroupent, elles, toujours entre
  // elles (`null === null`).
  it("ne fusionne pas une épreuve sans date avec une épreuve datée du même préfixe", () => {
    const groupes = groupEventsByCompetition([
      ev(1, `${PREFIXE} - A`, { event_date: null }),
      ev(2, `${PREFIXE} - B`, { event_date: "2026-06-13" }),
    ]);

    expect(groupes.map((g) => g.events.map((e) => e.id))).toEqual([[1], [2]]);
  });

  it("regroupe deux épreuves sans date partageant le même préfixe", () => {
    const groupes = groupEventsByCompetition([
      ev(1, `${PREFIXE} - A`, { event_date: null }),
      ev(2, `${PREFIXE} - B`, { event_date: null }),
    ]);

    expect(groupes).toHaveLength(1);
    expect(groupes[0].events.map((e) => e.id)).toEqual([1, 2]);
  });

  // Propriété que le cas 1 casse : la date que la ligne de groupe affiche
  // (`groupe.events[0].event_date`, EventList.tsx) doit valoir pour TOUTES
  // les épreuves qu'elle replie — sans quoi la ligne ment sur au moins l'une
  // d'entre elles. Survit à tout remaniement futur de la clé de groupe.
  it("propriété : la date affichée par un groupe vaut pour toutes les épreuves qu'il replie", () => {
    const echantillons: EventOut[][] = [
      [
        ev(1, `${PREFIXE} - A`, { event_date: "2026-06-13" }),
        ev(2, `${PREFIXE} - B`, { event_date: "2026-06-13" }),
        ev(3, `${PREFIXE} - C`, { event_date: "2026-06-13" }),
      ],
      [
        ev(1, "Triathlon de Mesquer", { event_date: "2026-05-16" }),
        ev(2, "Triathlon de Mesquer", { event_date: "2025-05-17" }),
      ],
      [
        ev(1, `${PREFIXE} - A`, { event_date: null }),
        ev(2, `${PREFIXE} - B`, { event_date: null }),
        ev(3, `${PREFIXE} - C`, { event_date: "2026-06-13" }),
      ],
      [
        ev(1, "Trail de Nantes", { event_date: "2026-01-10" }),
        ev(2, `${PREFIXE} - A`, { event_date: "2026-06-13" }),
        ev(3, `${PREFIXE} - B`, { event_date: "2026-06-13" }),
        ev(4, `${PREFIXE} - C`, { event_date: "2025-06-14" }),
      ],
    ];

    for (const events of echantillons) {
      const groupes = groupEventsByCompetition(events);
      for (const groupe of groupes) {
        const datesDistinctes = new Set(groupe.events.map((e) => e.event_date));
        expect(datesDistinctes.size).toBe(1);
        expect(groupe.events.every((e) => e.event_date === groupe.events[0].event_date)).toBe(true);
      }
    }
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
