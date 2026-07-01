import { describe, it, expect } from "vitest";
import { formatEventName } from "./event";

describe("formatEventName", () => {
  it("suffixe « (Relais) » quand isRelay est vrai", () => {
    expect(formatEventName("Triathlon de Nantes", true)).toBe("Triathlon de Nantes (Relais)");
  });
  it("renvoie le nom inchangé quand isRelay est faux", () => {
    expect(formatEventName("Triathlon de Nantes", false)).toBe("Triathlon de Nantes");
  });
});
