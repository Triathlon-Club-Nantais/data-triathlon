import { describe, it, expect } from "vitest";
import type { Participation } from "@/lib/types";
import { resumeAthlete, SEUIL_TUILES_COMPLETES } from "./athlete-stats";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
      ...(over.course ?? {}),
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time === undefined ? "01:59:00" : over.total_time,
    status: "finisher",
    is_relay: false,
    is_pending_validation: over.is_pending_validation ?? false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  } as Participation;
}

const tuile = (r: ReturnType<typeof resumeAthlete>, label: string) =>
  r.tuiles.find((t) => t.label === label);

describe("resumeAthlete — régimes (#488, PROF-4)", () => {
  it("aucune participation : régime vide, aucune tuile", () => {
    const r = resumeAthlete([]);

    expect(r.regime).toBe("vide");
    expect(r.tuiles).toEqual([]);
    expect(r.enAttente).toBe(0);
  });

  it("que des participations en attente : régime vide, mais le compte en attente est porté", () => {
    const r = resumeAthlete([part({ id: 1, is_pending_validation: true })]);

    expect(r.regime).toBe("vide");
    expect(r.validees).toHaveLength(0);
    expect(r.enAttente).toBe(1);
  });

  it(`${SEUIL_TUILES_COMPLETES} épreuves validées : régime complet, la page garde ses cinq tuiles`, () => {
    const r = resumeAthlete([part({ id: 1 }), part({ id: 2 }), part({ id: 3 })]);

    expect(r.regime).toBe("complet");
    expect(r.tuiles).toEqual([]);
    expect(r.validees).toHaveLength(3);
  });

  it("une épreuve validée avec temps : Épreuves, Discipline, Temps — et rien d'autre", () => {
    const r = resumeAthlete([
      part({ id: 1, total_time: "01:02:03", course: { name: "Triathlon de Nantes" } as Participation["course"] }),
    ]);

    expect(r.regime).toBe("reduit");
    expect(r.tuiles.map((t) => t.label)).toEqual(["Épreuves", "Discipline", "Temps"]);
    expect(tuile(r, "Épreuves")).toMatchObject({ value: "1", hint: null });
    expect(tuile(r, "Discipline")).toMatchObject({ value: "M", hint: "Triathlon de Nantes" });
    expect(tuile(r, "Temps")).toMatchObject({ value: "01:02:03", hint: "16/05/2026" });
    // Le critère central de PROF-4 : aucune tuile ne rend un tiret nu.
    expect(r.tuiles.every((t) => t.value !== "—")).toBe(true);
  });

  it("sans temps mais avec un rang : la tuile Temps devient Place, rapportée au champ", () => {
    const r = resumeAthlete([part({ id: 1, total_time: null, rank_overall: 12, course_finishers: 300 })]);

    expect(r.tuiles.map((t) => t.label)).toEqual(["Épreuves", "Discipline", "Place"]);
    expect(tuile(r, "Place")).toMatchObject({ value: "12e", hint: "sur 300 classés" });
  });

  it("sans temps ni rang : ni Temps ni Place, jamais un tiret", () => {
    const r = resumeAthlete([part({ id: 1, total_time: null, rank_overall: null })]);

    expect(r.tuiles.map((t) => t.label)).toEqual(["Épreuves", "Discipline"]);
  });

  it("discipline non reconnue : la tuile est omise plutôt que rendue vide", () => {
    const r = resumeAthlete([
      part({ id: 1, course: { event_type: "", distance_km: null } as unknown as Participation["course"] }),
    ]);

    expect(tuile(r, "Discipline")).toBeUndefined();
  });

  it("deux épreuves : les tuiles portent la plus récente", () => {
    const r = resumeAthlete([
      part({ id: 1, total_time: "05:00:00", course: { event_date: "2024-03-01", name: "Ancienne" } as Participation["course"] }),
      part({ id: 2, total_time: "04:00:00", course: { event_date: "2026-06-01", name: "Récente" } as Participation["course"] }),
    ]);

    expect(r.regime).toBe("reduit");
    expect(tuile(r, "Discipline")?.hint).toBe("Récente");
    expect(tuile(r, "Temps")?.value).toBe("04:00:00");
  });

  it("aucune participation : derniere vaut null", () => {
    const r = resumeAthlete([]);

    expect(r.derniere).toBeNull();
  });

  it("deux participations à la même date : la dernière du tableau départage (#488, revue finale)", () => {
    const p1 = part({ id: 1, course: { event_date: "2026-05-16", name: "Relais" } as Participation["course"] });
    const p2 = part({ id: 2, course: { event_date: "2026-05-16", name: "Individuel" } as Participation["course"] });
    const r = resumeAthlete([p1, p2]);

    expect(r.derniere).toBe(p2);
  });

  it(`régime complet (${SEUIL_TUILES_COMPLETES} épreuves) : derniere est aussi calculée`, () => {
    const p1 = part({ id: 1, course: { event_date: "2026-01-01" } as Participation["course"] });
    const p2 = part({ id: 2, course: { event_date: "2026-06-01" } as Participation["course"] });
    const p3 = part({ id: 3, course: { event_date: "2026-03-01" } as Participation["course"] });
    const r = resumeAthlete([p1, p2, p3]);

    expect(r.regime).toBe("complet");
    expect(r.derniere).toBe(p2);
  });

  it("les participations en attente ne comptent ni dans le régime ni dans les tuiles", () => {
    const r = resumeAthlete([
      part({ id: 1, total_time: "01:00:00" }),
      part({ id: 2, is_pending_validation: true }),
      part({ id: 3, is_pending_validation: true }),
    ]);

    expect(r.regime).toBe("reduit");
    expect(tuile(r, "Épreuves")).toMatchObject({ value: "1", hint: "2 en attente de validation" });
  });
});
