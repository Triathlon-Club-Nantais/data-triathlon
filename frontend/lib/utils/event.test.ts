import { describe, it, expect } from "vitest";
import type { EventOut } from "@/lib/types";
import { formatEventName, pendingOnlyLabel, sortEventsByDateDesc } from "./event";

describe("formatEventName", () => {
  it("suffixe « (Relais) » quand isRelay est vrai", () => {
    expect(formatEventName("Triathlon de Nantes", true)).toBe("Triathlon de Nantes (Relais)");
  });
  it("renvoie le nom inchangé quand isRelay est faux", () => {
    expect(formatEventName("Triathlon de Nantes", false)).toBe("Triathlon de Nantes");
  });
});

const BASE: EventOut = {
  id: 1,
  event_name: "E",
  event_date: null,
  event_type: "Triathlon S",
  is_relay: false,
  distance_km: null,
  total: 1,
  tcn_count: 1,
};

describe("sortEventsByDateDesc", () => {
  it("trie par date décroissante", () => {
    const events = [
      { ...BASE, id: 1, event_date: "2026-01-01" },
      { ...BASE, id: 2, event_date: "2026-06-01" },
      { ...BASE, id: 3, event_date: "2026-03-01" },
    ];
    expect(sortEventsByDateDesc(events).map((e) => e.id)).toEqual([2, 3, 1]);
  });

  it("relègue les épreuves sans date en fin de liste", () => {
    const events = [
      { ...BASE, id: 1, event_date: null },
      { ...BASE, id: 2, event_date: "2026-06-01" },
    ];
    expect(sortEventsByDateDesc(events).map((e) => e.id)).toEqual([2, 1]);
  });

  it("ne modifie pas le tableau d'origine", () => {
    const events = [
      { ...BASE, id: 1, event_date: "2026-01-01" },
      { ...BASE, id: 2, event_date: "2026-06-01" },
    ];
    const original = [...events];
    sortEventsByDateDesc(events);
    expect(events).toEqual(original);
  });
});

describe("pendingOnlyLabel (#1273)", () => {
  it("dit le nombre de résultats en attente d'une épreuve sans résultat validé", () => {
    expect(pendingOnlyLabel(0, 1)).toBe("1 résultat en attente");
    expect(pendingOnlyLabel(0, 2)).toBe("2 résultats en attente");
  });

  it("ne dit rien quand l'épreuve a des résultats validés ou rien en attente", () => {
    expect(pendingOnlyLabel(3, 1)).toBeNull();
    expect(pendingOnlyLabel(0, 0)).toBeNull();
    expect(pendingOnlyLabel(0, undefined)).toBeNull();
  });
});
