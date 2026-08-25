"use client";
import { useCallback, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { importEventStream } from "@/lib/api/sse";
import type { HeatFailure, ImportProgressEvent, ImportedCourse } from "@/lib/types";

export interface ImportState {
  running: boolean;
  phase: ImportProgressEvent["phase"] | "idle";
  message: string;
  total: number;
  progress: number;
  imported: number;
  updated: number;
  skipped: number;
  cached: boolean;
  // Progression par heat en phase `scraping` (fan-out Klikego #156).
  // Indice 1-based, `heatsScrapingTotal` = nombre de heats à scraper (hors cache
  // TTL par heat). Non renseigné = pas de fan-out, affiche le message classique.
  heatIndex: number;
  heatsScrapingTotal: number;
  heatLabel: string;
  heatSlug: string;
  // Progression phase C **dans** le heat en cours (#583) — participants dont
  // la page détail a été récupérée. 0/0 = pas encore rapportée (heat non
  // Klikego, ou pas assez avancé pour un premier lot).
  detailDone: number;
  detailTotal: number;
  // Courses touchées par le dernier import : câble « Voir les résultats » (#135).
  // Multi (heats, listes) → autant d'entrées. Vide en dehors de la phase `done`.
  courses: ImportedCourse[];
  // Fan-out Klikego (#156) — 5 clés remplies en phase `done`.
  heatsEnumerated: number;
  heatsImported: number;
  heatsCached: number;
  heatsFailed: number;
  failures: HeatFailure[];
  error: string | null;
  // Cause de l'échec, et non plus son seul message (#491) : `null` = le flux
  // s'est ouvert puis a annoncé un échec de lecture (le seul cas où l'URL est
  // en cause), `0` = coupure réseau, sinon le statut HTTP du refus. Trois
  // écrans distincts en dépendent, dont un seul signale le fournisseur.
  errorStatus: number | null;
  // Secondes à attendre avant un nouvel essai (en-tête `Retry-After` du 429).
  retryAfter: number | null;
}

const INITIAL: ImportState = {
  running: false,
  phase: "idle",
  message: "",
  total: 0,
  progress: 0,
  imported: 0,
  updated: 0,
  skipped: 0,
  cached: false,
  heatIndex: 0,
  heatsScrapingTotal: 0,
  heatLabel: "",
  heatSlug: "",
  detailDone: 0,
  detailTotal: 0,
  courses: [],
  heatsEnumerated: 0,
  heatsImported: 0,
  heatsCached: 0,
  heatsFailed: 0,
  failures: [],
  error: null,
  errorStatus: null,
  retryAfter: null,
};

export function useImportStream() {
  const [state, setState] = useState<ImportState>(INITIAL);
  // Le contrôleur de l'import en cours — et, du même coup, le verrou : non
  // nul = un import tourne. `courant()` distingue « c'est toujours mon flux »
  // de « on m'a annulé, ou un autre import a démarré », pour qu'un flux
  // abandonné n'écrive plus dans l'état qu'il ne possède plus.
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async (url: string) => {
    if (abortRef.current) return;
    const controle = new AbortController();
    abortRef.current = controle;
    const courant = () => abortRef.current === controle;
    setState({ ...INITIAL, running: true, phase: "scraping", message: "Récupération des participants…" });
    try {
      for await (const ev of importEventStream(url, controle.signal)) {
        if (!courant()) return;
        if (ev.phase === "scraping") {
          setState((s) => ({
            ...s,
            phase: "scraping",
            message: ev.message ?? s.message,
            heatIndex: ev.heat_index ?? s.heatIndex,
            heatsScrapingTotal: ev.heats_total ?? s.heatsScrapingTotal,
            heatLabel: ev.heat_label ?? s.heatLabel,
            heatSlug: ev.heat_slug ?? s.heatSlug,
            // Un nouveau heat (heat_index sans detail_done, l'event
            // `on_heat_start`) remet la progression de phase C à zéro : sans
            // ça, le heat suivant afficherait encore le compte du précédent.
            detailDone: ev.detail_done ?? (ev.heat_index !== undefined ? 0 : s.detailDone),
            detailTotal: ev.detail_total ?? (ev.heat_index !== undefined ? 0 : s.detailTotal),
          }));
        } else if (ev.phase === "saving") {
          setState((s) => ({
            ...s,
            phase: "saving",
            total: ev.total,
            progress: ev.progress,
            imported: ev.imported,
            updated: ev.updated,
            skipped: ev.skipped,
          }));
        } else if (ev.phase === "done") {
          setState((s) => ({
            ...s,
            running: false,
            phase: "done",
            total: ev.total,
            progress: ev.total,
            imported: ev.imported,
            updated: ev.updated,
            skipped: ev.skipped,
            cached: Boolean(ev.cached),
            courses: ev.courses ?? [],
            heatsEnumerated: ev.heats_enumerated ?? 0,
            heatsImported: ev.heats_imported ?? 0,
            heatsCached: ev.heats_cached ?? 0,
            heatsFailed: ev.heats_failed ?? 0,
            failures: ev.failures ?? [],
          }));
        } else if (ev.phase === "error") {
          setState((s) => ({ ...s, running: false, phase: "error", error: ev.message }));
        }
      }
    } catch (e) {
      // Une annulation fait lever l'`AbortError` du fetch : ce n'est pas une
      // panne, et `cancel` a déjà remis l'écran d'où il vient plutôt que
      // d'accuser un chronométreur qui n'a rien fait.
      if (!courant()) return;
      setState((s) => ({
        ...s,
        running: false,
        phase: "error",
        error: (e as Error).message,
        errorStatus: e instanceof ApiError ? e.status : 0,
        retryAfter: e instanceof ApiError ? e.retryAfter : null,
      }));
    } finally {
      if (courant()) abortRef.current = null;
    }
  }, []);

  /** Coupe le flux en cours et rend la main. Sans effet si rien ne tourne.
   *  Le verrou est levé ici, sans attendre que le flux veuille bien finir :
   *  un scrape muet retiendrait sinon le formulaire indéfiniment. */
  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(INITIAL);
  }, []);

  const reset = useCallback(() => setState(INITIAL), []);

  return { state, start, cancel, reset };
}
