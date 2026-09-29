import { describe, it, expect } from "vitest";
import { PARTICIPATION_STATUSES, participationStatusLabel } from "./labels";

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

  it("couvre les quatre statuts de participation", () => {
    expect(PARTICIPATION_STATUSES).toEqual(["finisher", "DNF", "DNS", "DSQ"]);
  });
});
