import { describe, expect, it } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";
import {
  brouillonDepuis,
  erreurDeSaisie,
  estSale,
  planEnregistrement,
  rebaser,
} from "./brouillon";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const AUTRE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

describe("brouillonDepuis", () => {
  it("rend les champs absents en chaîne vide plutôt qu'en null", () => {
    const b = brouillonDepuis(participation({ bib_number: null, rank_overall: null, club: null, category: null }));
    expect(b).toEqual({
      nom_epreuve: "Triathlon de Nantes",
      bib_number: "",
      rank_overall: "",
      club: "",
      category: "",
      athlete_cible: null,
    });
  });
});

describe("estSale", () => {
  it("est faux sur un brouillon jamais touché", () => {
    const p = participation();
    expect(estSale(brouillonDepuis(p), p)).toBe(false);
  });

  it("est vrai dès qu'un champ diverge", () => {
    const p = participation();
    expect(estSale({ ...brouillonDepuis(p), bib_number: "413" }, p)).toBe(true);
  });

  it("est vrai dès qu'un athlète cible est choisi", () => {
    const p = participation();
    expect(estSale({ ...brouillonDepuis(p), athlete_cible: AUTRE }, p)).toBe(true);
  });

  it("ignore un athlète cible identique à l'athlète courant", () => {
    const p = participation();
    expect(estSale({ ...brouillonDepuis(p), athlete_cible: ATHLETE }, p)).toBe(false);
  });
});

describe("erreurDeSaisie", () => {
  it("refuse un nom d'épreuve vide", () => {
    const b = { ...brouillonDepuis(participation()), nom_epreuve: "   " };
    expect(erreurDeSaisie(b)).toBe("Le nom de l'épreuve ne peut pas être vide.");
  });

  it("refuse une place au général qui n'est pas un entier positif", () => {
    const b = { ...brouillonDepuis(participation()), rank_overall: "0" };
    expect(erreurDeSaisie(b)).toBe("La place au général doit être un entier supérieur à zéro.");
  });

  it("accepte une place au général vide", () => {
    const b = { ...brouillonDepuis(participation()), rank_overall: "" };
    expect(erreurDeSaisie(b)).toBeNull();
  });
});

describe("planEnregistrement", () => {
  it("ne produit aucune étape sur un brouillon identique à l'origine", () => {
    const p = participation();
    expect(planEnregistrement(brouillonDepuis(p), p)).toEqual([]);
  });

  it("n'envoie que les champs qui ont bougé", () => {
    const p = participation();
    const plan = planEnregistrement({ ...brouillonDepuis(p), bib_number: "413" }, p);
    expect(plan).toEqual([{ type: "champs", champs: { bib_number: "413" } }]);
  });

  it("envoie null pour un champ effacé", () => {
    const p = participation();
    const plan = planEnregistrement({ ...brouillonDepuis(p), club: "" }, p);
    expect(plan).toEqual([{ type: "champs", champs: { club: null } }]);
  });

  it("convertit la place au général en nombre", () => {
    const p = participation();
    const plan = planEnregistrement({ ...brouillonDepuis(p), rank_overall: "12" }, p);
    expect(plan).toEqual([{ type: "champs", champs: { rank_overall: 12 } }]);
  });

  it("ordonne renommage, puis champs, puis réattribution", () => {
    const p = participation();
    const plan = planEnregistrement(
      { ...brouillonDepuis(p), nom_epreuve: "Triathlon de Nantes 2026", bib_number: "413", athlete_cible: AUTRE },
      p,
    );
    expect(plan.map((e) => e.type)).toEqual(["nom_epreuve", "champs", "reattribution"]);
    expect(plan[0]).toEqual({ type: "nom_epreuve", nom: "Triathlon de Nantes 2026" });
    expect(plan[2]).toEqual({ type: "reattribution", athleteId: 2 });
  });
});

describe("rebaser", () => {
  it("repose les champs enregistrés sur la participation renvoyée et garde les autres", () => {
    const p = participation();
    const sale = { ...brouillonDepuis(p), nom_epreuve: "Nouveau nom", bib_number: "413" };
    const apres = participation({ bib_number: "413" });

    const rebase = rebaser(sale, apres, ["champs"]);

    expect(rebase.bib_number).toBe("413");
    expect(estSale(rebase, apres)).toBe(true);
    expect(rebase.nom_epreuve).toBe("Nouveau nom");
  });

  it("efface l'athlète cible quand la réattribution est passée", () => {
    const p = participation();
    const sale = { ...brouillonDepuis(p), athlete_cible: AUTRE };
    expect(rebaser(sale, participation({ athlete: AUTRE }), ["reattribution"]).athlete_cible).toBeNull();
  });
});
