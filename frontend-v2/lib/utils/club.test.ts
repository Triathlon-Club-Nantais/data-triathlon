import { describe, it, expect } from "vitest";
import { isTCN } from "./club";

describe("isTCN", () => {
  it("reconnaît les variantes du club nantais", () => {
    expect(isTCN("TCN")).toBe(true);
    expect(isTCN("Triathlon Club Nantais")).toBe(true);
    expect(isTCN("Nantais Triathlon")).toBe(true);
  });
  it("est insensible à la casse", () => {
    expect(isTCN("triathlon club nant")).toBe(true);
  });
  it("renvoie false pour un autre club ou vide", () => {
    expect(isTCN("Stade Rennais")).toBe(false);
    expect(isTCN("")).toBe(false);
    expect(isTCN(null)).toBe(false);
  });
});
