import { describe, expect, it } from "vitest";
import { buildTicks, formatTickLabel, pickTickStep } from "./histogram-ticks";

// Raccourcis lisibles — secondes = minutes*60, heures*3600.
const m = (n: number) => n * 60;
const h = (n: number) => n * 3600;

describe("pickTickStep — pas de tick adapté à la durée (#129 AC2)", () => {
  it("sprint (~1 h) → pas de 15 min (4-5 ticks)", () => {
    // Une course de 55 min → 4 ticks à 15 min : [0, 15, 30, 45] (le 5e est
    // hors range).
    expect(pickTickStep(0, m(55))).toBe(m(15));
  });

  it("triathlon M (~2 h 30) → pas de 30 min", () => {
    // 2 h 30 = 150 min → 6 ticks à 30 min.
    expect(pickTickStep(0, m(150))).toBe(m(30));
  });

  it("triathlon L (~5-6 h) → pas d'1 h", () => {
    expect(pickTickStep(0, h(6))).toBe(h(1));
  });

  it("ironman (~10-15 h) → pas de 2 h", () => {
    expect(pickTickStep(0, h(14))).toBe(h(2));
  });

  it("dataset dégénéré (start = end) → pas fin sans crash", () => {
    // Toute la fenêtre est réduite à un point : on rend un pas quelconque
    // valide, jamais une division par zéro.
    expect(pickTickStep(m(30), m(30))).toBeGreaterThan(0);
  });
});

describe("buildTicks — alignement sur des heures rondes (#129 AC3)", () => {
  it("le 1er tick tombe sur un multiple du pas ≥ startSec", () => {
    // Sprint qui démarre à 1 h 07 min et se termine à 1 h 45 min. Le 1er
    // tick ne doit PAS être 1:07:00 — il doit être 1:15 (le multiple de
    // 15 min ≥ 1 h 07 min).
    const ticks = buildTicks(m(67), m(105));
    expect(ticks[0]).toBe(m(75)); // 1:15
    // Tous les ticks tombent sur des multiples de 15 min (le pas choisi).
    for (const t of ticks) expect(t % m(15)).toBe(0);
  });

  it("dataset qui démarre pile sur un multiple du pas : le 1er tick est le start", () => {
    const ticks = buildTicks(m(30), m(150));
    expect(ticks[0]).toBe(m(30));
  });

  it("dataset qui termine à un multiple du pas : le dernier tick est le end", () => {
    const ticks = buildTicks(m(0), m(60));
    expect(ticks[ticks.length - 1]).toBe(m(60));
  });

  it("dataset dégénéré (start = end) → au moins un tick, jamais de crash", () => {
    // Une seule participation → l'histogramme est valide mais dégénéré.
    // On veut au moins un tick pour ne pas rendre un axe X vide.
    const ticks = buildTicks(m(90), m(90));
    expect(ticks.length).toBeGreaterThanOrEqual(0);
  });

  it("reste dans la borne de lisibilité (≤ 8 ticks)", () => {
    // Une course de 15 h ne doit pas rendre 45 labels serrés.
    expect(buildTicks(0, h(15)).length).toBeLessThanOrEqual(8);
  });
});

describe("formatTickLabel — format court H:MM (#129 AC1)", () => {
  it("padde les minutes à 2 chiffres, pas les heures", () => {
    expect(formatTickLabel(m(75))).toBe("1:15");
    expect(formatTickLabel(m(90))).toBe("1:30");
    expect(formatTickLabel(h(8) + m(30))).toBe("8:30");
    // Une minute isolée doit être « 1:01 », pas « 1:1 ».
    expect(formatTickLabel(h(1) + m(1))).toBe("1:01");
  });

  it("gère 0 sans padding fantôme", () => {
    expect(formatTickLabel(0)).toBe("0:00");
  });

  it("arrondit à la seconde entière (les ticks tombent sur des minutes)", () => {
    expect(formatTickLabel(m(75) + 29)).toBe("1:15"); // 29s < 30 → tronqué à la minute
  });
});
