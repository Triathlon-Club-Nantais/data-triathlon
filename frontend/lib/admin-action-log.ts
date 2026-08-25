/**
 * Traduction des gestes et des payloads du journal d'administration (#501).
 *
 * Deux dictionnaires plats, sur le patron de `lib/sport-colors.ts` : source
 * unique, pas de logique par geste. `actionLabel` traduit le **code**
 * (`AdminActionLog.action`) ; `formatPayload` traduit les **clés** du JSON
 * libre qu'un geste a consigné, quel que soit le geste.
 */

const ACTION_LABELS: Record<string, string> = {
  "course.delete": "Suppression d'une épreuve",
  "course.update": "Correction d'une épreuve",
  "course.merge": "Fusion de deux épreuves",
  "course.source.switch": "Bascule de la source active",
  "course.rescrape": "Re-scrape d'une épreuve",
  "course.reliability": "Fiabilité tranchée manuellement",
  "courses.wipe_all": "Purge totale des épreuves",
  "participations.wipe_all": "Purge totale des résultats",
  "participation.reassign": "Réattribution d'un résultat",
  "participation.delete": "Suppression d'un résultat",
  "participation.validate": "Validation d'un résultat en attente",
  "participation.reject": "Rejet d'un résultat en attente",
  "participation.unreject": "Annulation d'un rejet",
  "participation.correct_fields": "Correction d'un résultat en attente",
  "athlete.update": "Correction d'une fiche coureur",
};

/** Le libellé français d'un geste, ou son code brut si le catalogue l'ignore. */
export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

const PAYLOAD_KEY_LABELS: Record<string, string> = {
  nom: "Nom",
  prenom: "Prénom",
  birth_date: "Date de naissance",
  club: "Club",
  name: "Nom de l'épreuve",
  event_date: "Date",
  event_type: "Type",
  is_relay: "Relais",
  bib_number: "Dossard",
  rank_overall: "Place au général",
  category: "Catégorie",
  participations_deleted: "Résultats détruits",
  athletes_purged: "Fiches coureur purgées",
  courses_deleted: "Épreuves détruites",
  courses_reset: "Épreuves remises en attente de rescrape",
  previous_url: "Ancienne URL",
  new_url: "Nouvelle URL",
  participations_imported: "Résultats importés",
  source_url: "URL de la source",
  imported: "Importés",
  updated: "Mis à jour",
  skipped: "Ignorés",
  reconciled: "Rapprochés",
  course_id: "Épreuve",
  from_athlete_id: "Depuis le coureur",
  to_athlete_id: "Vers le coureur",
  athlete_id: "Coureur",
  athlete_name: "Nom du coureur",
  course_name: "Nom de l'épreuve",
  total_time: "Temps total",
  status: "Statut",
  was_pending_validation: "Était en attente de validation",
  source_added: "Source ajoutée",
  absorbed: "Épreuve absorbée",
  id: "Identifiant",
  notes: "Note",
  computed: "Verdict calculé",
};

function labelFor(key: string): string {
  return PAYLOAD_KEY_LABELS[key] ?? key;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "oui" : "non";
  if (isRecord(v)) {
    return Object.entries(v)
      .map(([k, vv]) => `${labelFor(k)} : ${formatValue(vv)}`)
      .join(", ");
  }
  return String(v);
}

/**
 * Le détail lisible d'une entrée : un diff `avant → après` quand le payload
 * en porte un, sinon une ligne par clé restante — clé traduite si connue,
 * brute sinon.
 */
export function formatPayload(
  payload: Record<string, unknown> | null,
): { label: string; value: string }[] {
  if (!payload) return [];

  const { before, after, ...reste } = payload;
  const lignes: { label: string; value: string }[] = [];

  if (before !== undefined && after !== undefined) {
    if (isRecord(before) && isRecord(after)) {
      const champs = new Set([...Object.keys(before), ...Object.keys(after)]);
      for (const champ of champs) {
        if (JSON.stringify(before[champ]) !== JSON.stringify(after[champ])) {
          lignes.push({
            label: labelFor(champ),
            value: `${formatValue(before[champ])} → ${formatValue(after[champ])}`,
          });
        }
      }
    } else {
      lignes.push({
        label: "Modification",
        value: `${formatValue(before)} → ${formatValue(after)}`,
      });
    }
  }

  for (const [k, v] of Object.entries(reste)) {
    lignes.push({ label: labelFor(k), value: formatValue(v) });
  }

  return lignes;
}
