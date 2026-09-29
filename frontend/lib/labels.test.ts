import { describe, it, expect } from "vitest";
import { PARTICIPATION_STATUSES, participationStatusCount, participationStatusLabel } from "./labels";

// #1084 : une seule graphie par statut, de la saisie à la lecture.
describe("participationStatusLabel", () => {
  it.each([
    ["finisher", "Arrivé", "Arrivants"],
    ["DNF", "Abandon", "Abandons"],
    ["DNS", "Non partant", "Non-partants"],
    ["DSQ", "Disqualifié", "Disqualifiés"],
  ] as const)("%s se dit « %s » au singulier et « %s » au pluriel", (status, one, many) => {
    expect(participationStatusLabel(status)).toBe(one);
    expect(participationStatusLabel(status, { form: "many" })).toBe(many);
  });

  // Un compte dit le nom, pas l'état : « 1 arrivant », jamais « 1 arrivé ».
  it.each([
    ["finisher", 1, "1 arrivant"],
    ["finisher", 3, "3 arrivants"],
    ["DNF", 0, "0 abandon"],
    ["DNF", 5, "5 abandons"],
    ["DNS", 1, "1 non-partant"],
    ["DNS", 2, "2 non-partants"],
    ["DSQ", 1, "1 disqualifié"],
  ] as const)("compte %s × %i en « %s »", (status, n, attendu) => {
    expect(participationStatusCount(status, n)).toBe(attendu);
  });

  it("couvre les quatre statuts de participation", () => {
    expect(PARTICIPATION_STATUSES).toEqual(["finisher", "DNF", "DNS", "DSQ"]);
  });
});
