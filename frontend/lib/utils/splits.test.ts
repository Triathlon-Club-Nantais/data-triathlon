import { describe, it, expect } from "vitest";
import { splitSegments } from "./splits";

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
