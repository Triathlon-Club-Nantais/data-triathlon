// Pas de `"use client"` ici : ce module n'est importé que par `AppNav`, qui
// porte la directive. L'ajouter en ferait un **point d'entrée** client, dont
// Next exige des props sérialisables — or ce composant prend deux callbacks.
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Avatar, Input, Modal } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { apiClient } from "@/lib/api/client";
import type { AthleteSearchResult } from "@/lib/types";

/**
 * Athlète retenu en session, mémorisé d'une visite à l'autre.
 *
 * `prenom` et `nom` restent **séparés**, comme l'API les donne. Les aplatir en
 * un seul libellé obligeait le rail à redécouper le prénom, et « Jean Gael »
 * y perdait sa seconde moitié quand « Jean-Gaël » passait entier (#264).
 */
export type PickedAthlete = { id: number; prenom: string; nom: string };

const STORE = "tcn-athlete";

/**
 * Émis sur `window` après toute écriture effective du stock, pour que
 * `AppNav` (ou tout autre abonné) se resynchronise sans rechargement de page
 * — notamment depuis le bouton de sélection de la page profil (#323). Pas de
 * payload : les abonnés relisent `readAthlete()`, seule source de vérité.
 */
export const ATHLETE_CHANGED_EVENT = "tcn-athlete-changed";

/**
 * Émis sur `window` pour demander l'ouverture de la palette de sélection
 * (#502, revue UI/UX item 11). Même forme que `ATHLETE_CHANGED_EVENT` — pas de
 * payload, l'abonné (`AppNav`, seul à porter l'état `pickerOpen`) réagit en
 * ouvrant sa propre modale. Premier appelant : la bande « Ma saison » du
 * tableau de bord, qui n'a par elle-même ni route ni état pour ouvrir la
 * palette quand l'athlète retenu a disparu ; #503 et #504 en auront besoin
 * aussi.
 */
export const OPEN_PICKER_EVENT = "tcn-athlete-open-picker";

/** Nom d'usage — `filter` couvre l'athlète dont un des deux champs est vide. */
export function nomComplet(athlete: { prenom: string; nom: string }): string {
  return [athlete.prenom, athlete.nom].filter(Boolean).join(" ");
}

/**
 * Le stock est éditable par l'utilisateur : une valeur JSON-valide mais de
 * mauvaise forme ferait planter l'affichage ou router vers
 * `/athletes/undefined`. On la traite comme une absence de choix — ce qui
 * couvre aussi les stocks écrits avant #264, de forme `{ id, name }` : leur
 * porteur re-sélectionne son athlète une fois.
 */
export function readAthlete(): PickedAthlete | null {
  try {
    const valeur: unknown = JSON.parse(window.localStorage.getItem(STORE) ?? "null");
    const candidat = valeur as PickedAthlete | null;
    return typeof candidat?.id === "number" &&
      typeof candidat?.prenom === "string" &&
      typeof candidat?.nom === "string"
      ? candidat
      : null;
  } catch {
    return null;
  }
}

export function writeAthlete(a: PickedAthlete) {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(a));
    window.dispatchEvent(new Event(ATHLETE_CHANGED_EVENT));
  } catch {
    /* mode privé, quota : le choix vaut alors pour la session en cours seule. */
  }
}

/** Relâche l'athlète retenu — bouton de la page profil (#323). */
export function clearAthlete() {
  try {
    window.localStorage.removeItem(STORE);
    window.dispatchEvent(new Event(ATHLETE_CHANGED_EVENT));
  } catch {
    /* mode privé, quota : rien à relâcher côté stock. */
  }
}

/** Abonnement au stock — référence stable, exigée par `useSyncExternalStore`. */
function subscribeAthlete(onChange: () => void): () => void {
  window.addEventListener(ATHLETE_CHANGED_EVENT, onChange);
  return () => window.removeEventListener(ATHLETE_CHANGED_EVENT, onChange);
}

/**
 * L'athlète affiché est-il l'athlète retenu ? Côté client uniquement.
 *
 * Le stock vit en `localStorage` : **aucun rendu serveur ne le connaît**.
 * L'arbitrage du cluster #467 est de le lire là où il vit plutôt que d'en
 * miroiter une copie en cookie — le détail du raisonnement est dans
 * `frontend/AGENTS.md`. `useSyncExternalStore` porte exactement les deux
 * instantanés que cela demande : `false` au rendu serveur, la lecture réelle
 * dès l'hydratation, et une resynchronisation sur l'événement du stock sans
 * `useEffect` ni état local.
 *
 * Un booléen, pas l'athlète : `getSnapshot` doit rendre une valeur stable d'un
 * appel à l'autre, or `readAthlete()` reconstruit un objet à chaque lecture.
 */
export function useIsSelectedAthlete(id: number): boolean {
  return useSyncExternalStore(
    subscribeAthlete,
    useCallback(() => readAthlete()?.id === id, [id]),
    () => false,
  );
}

/**
 * Dernier instantané du stock, mémorisé au niveau du module.
 *
 * `useSyncExternalStore` compare le retour de `getSnapshot` au précédent avec
 * `Object.is` : rendre le résultat de `readAthlete()`, qui reconstruit un
 * objet à chaque lecture, ferait rendre React en boucle. On ne ré-analyse donc
 * que si la chaîne brute a changé — la clé de cache est le texte du stock,
 * seule chose qui change vraiment.
 */
let cachedRaw: string | null = null;
let cachedAthlete: PickedAthlete | null = null;

function snapshotAthlete(): PickedAthlete | null {
  let brut: string | null;
  try {
    brut = window.localStorage.getItem(STORE);
  } catch {
    // Mode privé, quota : pas de stock lisible, donc pas d'athlète retenu.
    return null;
  }
  if (brut !== cachedRaw) {
    cachedRaw = brut;
    cachedAthlete = readAthlete();
  }
  return cachedAthlete;
}

/**
 * L'athlète retenu lui-même, côté client uniquement — le pendant de
 * `useIsSelectedAthlete` pour les écrans qui ont besoin de son **nom** et non
 * d'un booléen : la pastille de `/resultats`, le raccourci du rail, le saut
 * vers sa ligne dans un classement (#503) et la bande « Ma saison » du
 * tableau de bord (#502). Même arbitrage qu'en #467 : le stock se lit là où
 * il vit, jamais par un cookie miroir — `null` au rendu serveur, la lecture
 * réelle dès l'hydratation (`frontend/AGENTS.md:218-277`).
 */
export function useSelectedAthlete(): PickedAthlete | null {
  return useSyncExternalStore(subscribeAthlete, snapshotAthlete, () => null);
}

/** Nombre d'athlètes affichés — au-delà, la palette précise « trop de
 *  résultats » plutôt que d'en cacher silencieusement (défaut 4/5, #484). */
const PAGE_SIZE = 12;

/**
 * Recherche d'un athlète du club. Interroge l'API à partir de **2 caractères**,
 * après 250 ms de silence, et plafonne à 12 résultats.
 */
export function AthletePicker({
  onClose,
  onPick,
}: {
  onClose: () => void;
  onPick: (athlete: PickedAthlete) => void;
}) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<AthleteSearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRows([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const found = await apiClient.searchAthletes(q, PAGE_SIZE + 1);
        if (!cancelled) setRows(found);
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query]);

  return (
    <Modal
      eyebrow="Mon athlète"
      title="Sélectionnez votre nom"
      onClose={onClose}
      width={520}
      footer={
        <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", textAlign: "center" }}>
          Votre saison s&apos;affichera en tête du tableau de bord.
        </div>
      }
    >
      <Input
        icon={<span>⌕</span>}
        value={query}
        autoFocus
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher un nom…"
      />
      <div style={{ marginTop: 8 }}>
        {rows.slice(0, PAGE_SIZE).map((a) => {
          const fullName = nomComplet(a);
          const choisir = () => onPick({ id: a.id, prenom: a.prenom, nom: a.nom });
          return (
            <div
              key={a.id}
              role="button"
              tabIndex={0}
              aria-label={`Choisir ${fullName}`}
              onClick={choisir}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  choisir();
                }
              }}
              style={{ display: "flex", alignItems: "center", gap: 14, padding: "11px 14px", borderRadius: 12, cursor: "pointer" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--tcn-fill)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              onFocus={(e) => (e.currentTarget.style.background = "var(--tcn-fill)")}
              onBlur={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <Avatar name={fullName} size={40} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, color: "var(--tcn-ink)", fontSize: 15 }}>{fullName}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
                  {a.club ?? "Sans club"} · {a.participation_count} épreuve
                  {a.participation_count > 1 ? "s" : ""}
                </div>
              </div>
              <span style={{ color: "var(--tcn-text-disabled)", fontSize: 18 }}>→</span>
            </div>
          );
        })}
        {query.trim().length >= 2 && !loading && rows.length === 0 && (
          <EmptyState
            bare
            title="Aucun athlète trouvé"
            action={
              <button
                type="button"
                onClick={() => setQuery("")}
                style={{ background: "none", border: "none", padding: 0, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", cursor: "pointer" }}
              >
                Effacer la recherche
              </button>
            }
          />
        )}
        {query.trim().length < 2 && (
          <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Saisissez au moins 2 lettres de votre nom.
          </div>
        )}
      </div>
    </Modal>
  );
}
