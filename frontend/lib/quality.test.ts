import { describe, it, expect } from "vitest";
import { describeQualityIssues } from "./quality";

describe("describeQualityIssues", () => {
  it("rend une liste vide sur null / undefined / objet vide", () => {
    expect(describeQualityIssues(null)).toEqual([]);
    expect(describeQualityIssues(undefined)).toEqual([]);
    expect(describeQualityIssues({})).toEqual([]);
  });

  it("traduit les codes canoniques au singulier", () => {
    expect(describeQualityIssues({ duplicate_bib: 1 })).toEqual([
      "1 dossard en doublon dans les données du chronométreur",
    ]);
    expect(describeQualityIssues({ rank_gap: 1 })).toEqual(["1 trou dans le classement"]);
    expect(describeQualityIssues({ duplicate_rank: 1 })).toEqual([
      "1 rang partagé par plusieurs finishers",
    ]);
    expect(describeQualityIssues({ finisher_without_time: 1 })).toEqual(["1 finisher sans temps"]);
    expect(describeQualityIssues({ unknown_status: 1 })).toEqual(["1 statut hors nomenclature"]);
  });

  it("accorde le pluriel au-delà de un", () => {
    expect(describeQualityIssues({ duplicate_bib: 3 })).toEqual([
      "3 dossards en doublon dans les données du chronométreur",
    ]);
    expect(describeQualityIssues({ rank_gap: 5 })).toEqual(["5 trous dans le classement"]);
    expect(describeQualityIssues({ duplicate_rank: 2 })).toEqual([
      "2 rangs partagés par plusieurs finishers",
    ]);
    expect(describeQualityIssues({ finisher_without_time: 4 })).toEqual(["4 finishers sans temps"]);
    expect(describeQualityIssues({ unknown_status: 2 })).toEqual(["2 statuts hors nomenclature"]);
  });

  it("rend `no_participation` sans compteur (toujours 1)", () => {
    expect(describeQualityIssues({ no_participation: 1 })).toEqual([
      "Course importée sans participation",
    ]);
  });

  it("combine plusieurs anomalies dans l'ordre reçu", () => {
    expect(describeQualityIssues({ duplicate_bib: 2, rank_gap: 1 })).toEqual([
      "2 dossards en doublon dans les données du chronométreur",
      "1 trou dans le classement",
    ]);
  });

  it("rend un code inconnu tel quel (nouveau code backend en attente de trad)", () => {
    expect(describeQualityIssues({ future_anomaly: 7 })).toEqual(["future_anomaly: 7"]);
  });
});
