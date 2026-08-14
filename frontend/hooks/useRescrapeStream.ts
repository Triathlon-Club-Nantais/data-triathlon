"use client";
import { useCallback, useRef, useState } from "react";
import { rescrapeEventStream } from "@/lib/api/sse";
import type { RescrapeProgressEvent } from "@/lib/types";

export interface RescrapeState {
  running: boolean;
  phase: RescrapeProgressEvent["phase"] | "idle";
  message: string;
  total: number;
  progress: number;
  imported: number;
  updated: number;
  skipped: number;
  reconciled: number;
  orphansRemoved: number;
  error: string | null;
}

const INITIAL: RescrapeState = {
  running: false,
  phase: "idle",
  message: "",
  total: 0,
  progress: 0,
  imported: 0,
  updated: 0,
  skipped: 0,
  reconciled: 0,
  orphansRemoved: 0,
  error: null,
};

/** Patron de `useImportStream` — état géré à la main, pas de mutation React
 * Query (research.md R1) : un seul consommateur, le navigateur qui a cliqué. */
export function useRescrapeStream() {
  const [state, setState] = useState<RescrapeState>(INITIAL);
  const activeRef = useRef(false);

  const start = useCallback(async (courseId: number) => {
    if (activeRef.current) return;
    activeRef.current = true;
    setState({ ...INITIAL, running: true, phase: "scraping", message: "Récupération des participants…" });
    try {
      for await (const ev of rescrapeEventStream(courseId)) {
        if (ev.phase === "scraping") {
          setState((s) => ({
            ...s,
            phase: "scraping",
            message: ev.message ?? s.message,
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
            reconciled: ev.reconciled,
            orphansRemoved: ev.orphans_removed,
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
