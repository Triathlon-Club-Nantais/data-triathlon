import { describe, it, expect } from "vitest";
import { comparableSeconds, secondsFromHms } from "./time";

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

describe("comparableSeconds", () => {
  it("treats a zero time as absent, like the backend", () => {
    expect(comparableSeconds("00:00:00")).toBeNull();
    expect(comparableSeconds("0:00")).toBeNull();
  });
  it("keeps a real time and rejects an unreadable one", () => {
    expect(comparableSeconds("01:00:00")).toBe(3600);
    expect(comparableSeconds("abc")).toBeNull();
  });
});
