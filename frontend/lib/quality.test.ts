import { describe, it, expect } from "vitest";
import { describeQualityIssues, QUALITY_ISSUE_LABELS } from "./quality";

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

describe("QUALITY_ISSUE_LABELS", () => {
  it("nomme les six codes canoniques par un libellé nu, sans compteur", () => {
    expect(QUALITY_ISSUE_LABELS.duplicate_bib).toBe("Dossards en doublon");
    expect(QUALITY_ISSUE_LABELS.rank_gap).toBe("Trous dans le classement");
    expect(QUALITY_ISSUE_LABELS.duplicate_rank).toBe("Rangs partagés");
    expect(QUALITY_ISSUE_LABELS.finisher_without_time).toBe("Finishers sans temps");
    expect(QUALITY_ISSUE_LABELS.unknown_status).toBe("Statuts hors nomenclature");
    expect(QUALITY_ISSUE_LABELS.no_participation).toBe("Course importée sans participation");
  });

  it("n'a pas de libellé pour un code inconnu (repli sur le code brut à l'appelant)", () => {
    expect(QUALITY_ISSUE_LABELS.future_anomaly).toBeUndefined();
  });
});
