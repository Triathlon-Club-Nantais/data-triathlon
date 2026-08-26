"use client";
import { useCallback, useRef, useState } from "react";
import { switchSourceEventStream } from "@/lib/api/sse";
import type { CourseSource, SwitchSourceProgressEvent } from "@/lib/types";

export interface SwitchSourceState {
  running: boolean;
  phase: SwitchSourceProgressEvent["phase"] | "idle";
  message: string;
  total: number;
  participationsDeleted: number;
  participationsImported: number;
  athletesPurged: number;
  /** La liste à jour, portée par l'event `done` (#624) — `null` tant qu'aucun
   * flux n'a abouti, pour distinguer « pas encore de résultat » de « zéro
   * source », qui n'arrive jamais en pratique mais que `null` ne confond pas. */
  sources: CourseSource[] | null;
  error: string | null;
}

const INITIAL: SwitchSourceState = {
  running: false,
  phase: "idle",
  message: "",
  total: 0,
  participationsDeleted: 0,
  participationsImported: 0,
  athletesPurged: 0,
  sources: null,
  error: null,
};

/** Le dénouement du flux, pour que l'appelant réagisse dans son propre
 * gestionnaire d'événement plutôt que dans un `useEffect` sur `state.phase`
 * (React déconseille le `setState` synchrone en effet — cascading renders). */
type SwitchSourceResult =
  | { phase: "done"; sources: CourseSource[] }
  | { phase: "error"; message: string };

/** Patron de `useRescrapeStream` (#624) — état géré à la main, pas de
 * mutation React Query (research.md R1) : un seul consommateur, le
 * navigateur qui a cliqué « Basculer ». */
export function useSwitchSourceStream() {
  const [state, setState] = useState<SwitchSourceState>(INITIAL);
  const activeRef = useRef(false);

  const start = useCallback(
    async (courseId: number, sourceId: number): Promise<SwitchSourceResult | null> => {
      if (activeRef.current) return null;
      activeRef.current = true;
      setState({
        ...INITIAL,
        running: true,
        phase: "scraping",
        message: "Récupération des participants…",
      });
      let resultat: SwitchSourceResult | null = null;
      try {
        for await (const ev of switchSourceEventStream(courseId, sourceId)) {
          if (ev.phase === "scraping") {
            setState((s) => ({ ...s, phase: "scraping", message: ev.message ?? s.message }));
          } else if (ev.phase === "saving") {
            setState((s) => ({ ...s, phase: "saving", total: ev.total }));
          } else if (ev.phase === "done") {
            resultat = { phase: "done", sources: ev.sources };
            setState((s) => ({
              ...s,
              running: false,
              phase: "done",
              participationsDeleted: ev.participations_deleted,
              participationsImported: ev.participations_imported,
              athletesPurged: ev.athletes_purged,
              sources: ev.sources,
            }));
          } else if (ev.phase === "error") {
            resultat = { phase: "error", message: ev.message };
            setState((s) => ({ ...s, running: false, phase: "error", error: ev.message }));
          }
        }
      } catch (e) {
        const message = (e as Error).message;
        resultat = { phase: "error", message };
        setState((s) => ({ ...s, running: false, phase: "error", error: message }));
      } finally {
        activeRef.current = false;
      }
      return resultat;
    },
    [],
  );

  const reset = useCallback(() => setState(INITIAL), []);

  return { state, start, reset };
}
