"use client";
import { useCallback, useRef, useState } from "react";
import { importEventStream } from "@/lib/api/sse";
import type { ImportProgressEvent } from "@/lib/types";

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
          setState((s) => ({ ...s, phase: "scraping", message: ev.message }));
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
