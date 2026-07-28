import { describe, it, expect } from "vitest";
import { splitColumns, splitSegments } from "./splits";

describe("splitSegments", () => {
  it("triathlon : natation, T1, vélo, T2, course", () => {
    const splits = { swim: "00:20:00", t1: "00:01:00", bike: "01:00:00", t2: "00:00:45", run: "00:35:00" };
    const segs = splitSegments("triathlon-m", splits);
    expect(segs.map((s) => s.label)).toEqual(["Natation", "T1", "Vélo", "T2", "Course"]);
    expect(segs[0].time).toBe("00:20:00");
    expect(segs[1].small).toBe(true);
  });

  it("duathlon : Course 1, T1, Vélo, T2, Course 2", () => {
    // Le backend (mapping.build_splits) émet course1/course2, pas swim/run.
    const splits = { course1: "00:18:00", t1: "00:01:00", bike: "00:40:00", t2: "00:00:50", course2: "00:20:00" };
    const segs = splitSegments("duathlon-s", splits);
    expect(segs.map((s) => s.label)).toEqual(["Course 1", "T1", "Vélo", "T2", "Course 2"]);
    expect(segs.map((s) => s.time)).toEqual(["00:18:00", "00:01:00", "00:40:00", "00:00:50", "00:20:00"]);
  });

  it("bike-run : Vélo, Course", () => {
    const segs = splitSegments("bike-run", { bike: "00:30:00", run: "00:20:00" });
    expect(segs.map((s) => s.label)).toEqual(["Vélo", "Course"]);
  });

  it("aquathlon : Natation, Course", () => {
    const segs = splitSegments("aquathlon", { swim: "00:10:00", run: "00:20:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "Course"]);
  });

  it("aquarun : Natation, T1, Course", () => {
    const segs = splitSegments("aquarun", { swim: "00:10:00", t1: "00:01:00", run: "00:20:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "T1", "Course"]);
  });

  it("omet les segments sans temps", () => {
    const segs = splitSegments("triathlon-m", { swim: "00:20:00", run: "00:35:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "Course"]);
  });

  it("renvoie un tableau vide si splits est null", () => {
    expect(splitSegments("triathlon-m", null)).toEqual([]);
  });
});

// Les scrapers qui renseignent `segments` (ok-time, RaceResult, Chronoplace) clés
// leurs splits sur les **libellés de la source**, hors de tout schéma de sport :
// sans ce chemin, `splitSegments` rendait [] et aucun split ne s'affichait.
describe("splitSegments — splits étiquetés par la source", () => {
  const OKTIME = { NATATION: "00:23:56", VELO: "01:56:14", "COURSE A PIED": "01:11:47" };

  it("rend les segments de la source, dans son ordre", () => {
    const segs = splitSegments("triathlon-l", OKTIME);
    expect(segs.map((s) => s.label)).toEqual(["NATATION", "VELO", "COURSE A PIED"]);
    expect(segs.map((s) => s.time)).toEqual(["00:23:56", "01:56:14", "01:11:47"]);
  });

  it("colore selon la discipline devinée du libellé, neutre à défaut", () => {
    const segs = splitSegments("triathlon-l", { ...OKTIME, T2: "00:01:00", ENIGME: "00:05:00" });
    expect(segs.map((s) => s.color)).toEqual([
      "var(--swim)", "var(--bike)", "var(--run)",
      "var(--muted-foreground)", "var(--muted-foreground)",
    ]);
    expect(segs.find((s) => s.key === "T2")?.small).toBe(true);
    expect(segs.find((s) => s.key === "ENIGME")?.small).toBeUndefined();
  });

  it("laisse la main au schéma du sport dès qu'une de ses clés répond", () => {
    const segs = splitSegments("triathlon-m", { swim: "00:20:00", run: "00:35:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "Course"]);
  });
});

describe("splitColumns", () => {
  it("union des segments vus chez au moins un participant, dans l'ordre de la source", () => {
    const cols = splitColumns("triathlon-l", [
      { NATATION: "00:23:56" },
      { NATATION: "00:25:00", VELO: "01:56:14" },
      null,
    ]);

    expect(cols.map((c) => c.key)).toEqual(["NATATION", "VELO"]);
  });

  it("retombe sur le schéma du sport pour des splits canoniques", () => {
    const cols = splitColumns("triathlon-m", [{ swim: "00:20:00", bike: "01:00:00" }]);

    expect(cols.map((c) => c.label)).toEqual(["Natation", "Vélo"]);
  });

  it("n'ouvre aucune colonne sans splits", () => {
    expect(splitColumns("triathlon-m", [null, undefined, {}])).toEqual([]);
  });
});
