"use client";
import { useCallback, useRef, useState } from "react";
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
  courses: [],
  heatsEnumerated: 0,
  heatsImported: 0,
  heatsCached: 0,
  heatsFailed: 0,
  failures: [],
  error: null,
};

export function useImportStream() {
  const [state, setState] = useState<ImportState>(INITIAL);
  const activeRef = useRef(false);

  const start = useCallback(async (url: string) => {
    if (activeRef.current) return;
    activeRef.current = true;
    setState({ ...INITIAL, running: true, phase: "scraping", message: "Récupération des participants…" });
    try {
      for await (const ev of importEventStream(url)) {
        if (ev.phase === "scraping") {
          setState((s) => ({
            ...s,
            phase: "scraping",
            message: ev.message ?? s.message,
            heatIndex: ev.heat_index ?? s.heatIndex,
            heatsScrapingTotal: ev.heats_total ?? s.heatsScrapingTotal,
            heatLabel: ev.heat_label ?? s.heatLabel,
            heatSlug: ev.heat_slug ?? s.heatSlug,
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
      setState((s) => ({ ...s, running: false, phase: "error", error: (e as Error).message }));
    } finally {
      activeRef.current = false;
    }
  }, []);

  const reset = useCallback(() => setState(INITIAL), []);

  return { state, start, reset };
}
