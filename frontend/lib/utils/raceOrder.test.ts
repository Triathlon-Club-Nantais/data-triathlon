import { describe, it, expect } from "vitest";
import { isNonFinisher } from "./raceOrder";
describe("isNonFinisher", () => {
  it("reconnaît DNF/DNS/DSQ (toute casse) et rejette finisher/vide", () => {
    expect(isNonFinisher("DNF")).toBe(true);
    expect(isNonFinisher("dns")).toBe(true);
    expect(isNonFinisher("DSQ")).toBe(true);
    expect(isNonFinisher("finisher")).toBe(false);
    expect(isNonFinisher("")).toBe(false);
    expect(isNonFinisher(null)).toBe(false);
    expect(isNonFinisher(undefined)).toBe(false);
  });
});
