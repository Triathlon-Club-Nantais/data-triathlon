import { describe, it, expect } from "vitest";
import { gridColumns, gridMinWidth, type Track } from "./table";

const TRACKS: Track[] = [120, { flexMin: 200 }, 90, 28];

describe("gridColumns", () => {
  it("rend les pistes fixes en px et la piste souple en minmax", () => {
    expect(gridColumns(TRACKS)).toBe("120px minmax(200px, 1fr) 90px 28px");
  });
});

describe("gridMinWidth", () => {
  it("additionne les pistes, les gouttières et le padding latéral", () => {
    // 120 + 200 + 90 + 28 = 438 ; 3 gouttières de 18 = 54 ; padding 2 × 26 = 52.
    expect(gridMinWidth(TRACKS, { gap: 18, paddingX: 26 })).toBe(544);
  });

  it("compte la largeur minimale de la piste souple, jamais zéro", () => {
    const sansSouple: Track[] = [120, 90, 28];
    expect(gridMinWidth(TRACKS, { gap: 0, paddingX: 0 })).toBe(
      gridMinWidth(sansSouple, { gap: 0, paddingX: 0 }) + 200,
    );
  });
});
