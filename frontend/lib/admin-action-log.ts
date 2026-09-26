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
  "course_duplicate.ignore": "Paire de doublons suspects écartée",
  "course_source.delete": "Suppression d'une source d'épreuve",
  "participation.set_teammates": "Équipiers d'un relais attribués",
  "athlete.season_validation.create": "Validation d'une saison",
  "athlete.season_validation.delete": "Annulation de la validation d'une saison",
  "athlete.volunteer_action.accept": "Acceptation d'une déclaration de bénévolat",
  "athlete.volunteer_action.reject": "Refus d'une déclaration de bénévolat",
  "athlete.volunteer_action.delete": "Suppression d'une déclaration de bénévolat",
  "club_alias.add": "Ajout d'une variante de club",
  "club_alias.remove": "Retrait d'une variante de club",
  "counter_scope.entry_add": "Ajout d'un libellé à la portée des compteurs",
  "counter_scope.entry_remove": "Retrait d'un libellé de la portée des compteurs",
  "site_access.password_replace": "Remplacement du code d'accès au site",
  "benevole_access.password_replace": "Remplacement du mot de passe bénévoles",
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
  course_id_a: "Première épreuve",
  course_id_b: "Seconde épreuve",
  season: "Saison",
  action_id: "Déclaration de bénévolat",
  url: "URL",
  provider: "Fournisseur",
};

/** Clés qui désignent un coureur ou une épreuve : rendues en lien vers sa page. */
const LIEN_PAR_CLE: Record<string, string> = {
  athlete_id: "/athletes",
  from_athlete_id: "/athletes",
  to_athlete_id: "/athletes",
  course_id: "/courses",
  course_id_a: "/courses",
  course_id_b: "/courses",
};

/** L'entité visée, pour les gestes qui ne consignent aucun payload. */
const ENTITES: Record<string, { label: string; href?: string }> = {
  athlete: { label: "Coureur", href: "/athletes" },
  course: { label: "Épreuve", href: "/courses" },
  participation: { label: "Résultat" },
  course_source: { label: "Source d'épreuve" },
  course_duplicate: { label: "Paire de doublons" },
  club_alias: { label: "Variante de club" },
  counter_scope_entry: { label: "Libellé de la portée des compteurs" },
  site_access_config: { label: "Code d'accès au site" },
  benevole_access_config: { label: "Mot de passe bénévoles" },
};

export type LigneDetail = { label: string; value: string; href?: string };

function labelFor(key: string): string {
  return PAYLOAD_KEY_LABELS[key] ?? key;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "oui" : "non";
  if (Array.isArray(v)) {
    return v.length === 0 ? "aucun" : `${v.length} (${v.map((item) => formatValue(item)).join(", ")})`;
  }
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
export function formatPayload(payload: Record<string, unknown> | null): LigneDetail[] {
  if (!payload) return [];

  const { before, after, ...reste } = payload;
  const lignes: LigneDetail[] = [];

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
    const base = LIEN_PAR_CLE[k];
    lignes.push(
      base && typeof v === "number"
        ? { label: labelFor(k), value: String(v), href: `${base}/${v}` }
        : { label: labelFor(k), value: formatValue(v) },
    );
  }

  return lignes;
}

/**
 * Le détail d'une entrée du journal : son payload traduit, ou à défaut
 * l'entité qu'elle vise, pour qu'aucune ligne ne reste muette (#1043).
 */
export function detailLines(entree: {
  entity_type: string;
  entity_id: number;
  payload: Record<string, unknown> | null;
}): LigneDetail[] {
  const lignes = formatPayload(entree.payload);
  if (lignes.length > 0) return lignes;
  const entite = ENTITES[entree.entity_type];
  if (!entite) return [{ label: entree.entity_type, value: `n° ${entree.entity_id}` }];
  return entite.href
    ? [{ label: entite.label, value: String(entree.entity_id), href: `${entite.href}/${entree.entity_id}` }]
    : [{ label: entite.label, value: `n° ${entree.entity_id}` }];
}
