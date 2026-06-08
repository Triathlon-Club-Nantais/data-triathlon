import { describe, it, expect } from "vitest";
import { secondsFromHms } from "./time";

describe("secondsFromHms", () => {
  it("convertit HH:MM:SS en secondes", () => {
    expect(secondsFromHms("01:00:00")).toBe(3600);
    expect(secondsFromHms("00:01:30")).toBe(90);
  });
  it("gère MM:SS", () => {
    expect(secondsFromHms("02:30")).toBe(150);
  });
  it("renvoie null si vide ou invalide", () => {
    expect(secondsFromHms("")).toBeNull();
    expect(secondsFromHms("abc")).toBeNull();
  });
});
