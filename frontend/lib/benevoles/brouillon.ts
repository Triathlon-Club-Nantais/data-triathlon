import type { AthleteBrief, Participation } from "@/lib/types";

/** Formulaire unique du panneau bénévole (#490, PROF-10) : un seul état,
 *  un seul enregistrement. Ce module est **pur** — ni React, ni réseau — pour
 *  que l'ordre des appels et le rattrapage d'un échec partiel se testent sans
 *  monter d'écran. */
export type Brouillon = {
  nom_epreuve: string;
  /** Chaînes et non nombres : les champs sont des `<input>`, et « vide »
   *  (effacement demandé) ne s'exprime pas en `number`. */
  bib_number: string;
  rank_overall: string;
  club: string;
  category: string;
  /** `null` = aucune réattribution demandée. Le choix est **différé** : il
   *  n'écrit qu'à l'enregistrement. */
  athlete_cible: AthleteBrief | null;
};

export type ChampsModifies = {
  bib_number?: string | null;
  rank_overall?: number | null;
  club?: string | null;
  category?: string | null;
};

export type Etape =
  | { type: "nom_epreuve"; nom: string }
  | { type: "champs"; champs: ChampsModifies }
  | { type: "reattribution"; athleteId: number };

/** Ce que l'erreur affiche quand une étape échoue : une zone d'erreur unique
 *  doit dire *laquelle*. */
export const LIBELLE_ETAPE: Record<Etape["type"], string> = {
  nom_epreuve: "Le nom de l'épreuve n'a pas pu être enregistré",
  champs: "Les champs n'ont pas pu être enregistrés",
  reattribution: "La réattribution n'a pas pu être enregistrée",
};

/** Les quatre champs portés par `PATCH /benevoles/participations/{id}`. */
const CHAMPS = ["bib_number", "rank_overall", "club", "category"] as const;

function texte(valeur: string | number | null | undefined): string {
  return valeur == null ? "" : String(valeur);
}

export function brouillonDepuis(participation: Participation): Brouillon {
  return {
    nom_epreuve: participation.course.name,
    bib_number: texte(participation.bib_number),
    rank_overall: texte(participation.rank_overall),
    club: texte(participation.club),
    category: texte(participation.category),
    athlete_cible: null,
  };
}

export function estSale(brouillon: Brouillon, participation: Participation): boolean {
  const origine = brouillonDepuis(participation);
  const champDiverge = (["nom_epreuve", ...CHAMPS] as const).some(
    (cle) => brouillon[cle].trim() !== origine[cle].trim(),
  );
  const reattribue =
    brouillon.athlete_cible != null && brouillon.athlete_cible.id !== participation.athlete.id;
  return champDiverge || reattribue;
}

export function erreurDeSaisie(brouillon: Brouillon): string | null {
  if (!brouillon.nom_epreuve.trim()) {
    return "Le nom de l'épreuve ne peut pas être vide.";
  }
  const place = brouillon.rank_overall.trim();
  if (place && (!/^\d+$/.test(place) || Number(place) < 1)) {
    return "La place au général doit être un entier supérieur à zéro.";
  }
  return null;
}

export function planEnregistrement(brouillon: Brouillon, participation: Participation): Etape[] {
  const origine = brouillonDepuis(participation);
  const plan: Etape[] = [];

  const nom = brouillon.nom_epreuve.trim();
  if (nom && nom !== origine.nom_epreuve.trim()) {
    plan.push({ type: "nom_epreuve", nom });
  }

  const champs: ChampsModifies = {};
  for (const cle of CHAMPS) {
    const valeur = brouillon[cle].trim();
    if (valeur === origine[cle].trim()) continue;
    // `null` et non `""` : le backend est nullable partout, et effacer un
    // dossard est un geste légitime du bénévole.
    champs[cle] = (cle === "rank_overall" ? (valeur ? Number(valeur) : null) : valeur || null) as never;
  }
  if (Object.keys(champs).length > 0) {
    plan.push({ type: "champs", champs });
  }

  if (brouillon.athlete_cible && brouillon.athlete_cible.id !== participation.athlete.id) {
    plan.push({ type: "reattribution", athleteId: brouillon.athlete_cible.id });
  }

  return plan;
}

/** Après un échec partiel, ce qui est passé est commité côté serveur : on
 *  repose ces champs sur la participation renvoyée, et on ne garde sale que ce
 *  qui n'a pas pu partir. */
export function rebaser(
  brouillon: Brouillon,
  participation: Participation,
  reussies: Etape["type"][],
): Brouillon {
  const origine = brouillonDepuis(participation);
  const rebase = { ...brouillon };
  if (reussies.includes("nom_epreuve")) rebase.nom_epreuve = origine.nom_epreuve;
  if (reussies.includes("champs")) {
    for (const cle of CHAMPS) rebase[cle] = origine[cle];
  }
  if (reussies.includes("reattribution")) rebase.athlete_cible = null;
  return rebase;
}
