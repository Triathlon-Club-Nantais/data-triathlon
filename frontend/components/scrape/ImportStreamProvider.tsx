"use client";
import { useCallback, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { captureEvent } from "@/lib/posthog";
import { formatCount } from "@/lib/utils/format";
import {
  ImportStreamContext,
  useImportStreamController,
  type ImportState,
} from "@/hooks/useImportStream";

/**
 * L'import de résultats, tenu au niveau du layout (#1062). Une navigation
 * interne démonte `TcnScrapeForm` mais ne coupe pas la SSE : l'import va au
 * bout, et s'il finit **sans écran attaché**, ce provider l'annonce par un
 * toast global (succès, partiel ou échec, avec le lien vers l'épreuve). Le
 * verrou « un import à la fois » vit ici aussi : revenir sur `/ajouter`
 * remonte le formulaire sur le flux ouvert, sans pouvoir relancer la même URL.
 */
export function ImportStreamProvider({ children }: { children: ReactNode }) {
  const { state, url, start, cancel, reset } = useImportStreamController();
  const router = useRouter();
  const attaches = useRef(0);
  const etatRef = useRef(state);
  useEffect(() => {
    etatRef.current = state;
  }, [state]);

  const attach = useCallback(() => {
    attaches.current += 1;
    return () => {
      attaches.current -= 1;
      // Un bilan déjà affiché ne se rejoue pas au retour sur l'écran.
      if (attaches.current === 0 && !etatRef.current.running) reset();
    };
  }, [reset]);

  const phasePrecedente = useRef(state.phase);
  useEffect(() => {
    const avant = phasePrecedente.current;
    phasePrecedente.current = state.phase;
    if (avant === state.phase || (state.phase !== "done" && state.phase !== "error")) return;
    if (attaches.current > 0) return;
    annoncer(state, (href) => router.push(href));
    reset();
  }, [state, router, reset]);

  // Fermer l'onglet, lui, coupe la SSE à mi-course, où que l'on soit.
  useEffect(() => {
    if (!state.running) return;
    const garde = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", garde);
    return () => window.removeEventListener("beforeunload", garde);
  }, [state.running]);

  const valeur = useMemo(
    () => ({ state, url, start, cancel, reset, attach }),
    [state, url, start, cancel, reset, attach],
  );
  return <ImportStreamContext.Provider value={valeur}>{children}</ImportStreamContext.Provider>;
}

function annoncer(state: ImportState, aller: (href: string) => void) {
  if (state.phase === "error") {
    captureEvent("results_import_failed", { error_message: state.error ?? "Import impossible" });
    toast.error("L'import a échoué", {
      description: state.error ?? "Import impossible",
      action: { label: "Reprendre", onClick: () => aller("/ajouter") },
    });
    return;
  }
  captureEvent("results_import_completed", {
    imported_count: state.imported,
    skipped_count: state.skipped,
    course_count: state.courses.length,
  });
  const epreuve = state.courses[0];
  const action = epreuve
    ? { label: "Voir l'épreuve", onClick: () => aller(`/courses/${epreuve.id}`) }
    : undefined;
  const bilan = `${formatCount(state.imported)} importés, ${formatCount(state.updated)} mis à jour, ${formatCount(state.skipped)} ignorés.`;
  if (state.failures.length > 0) {
    const perdues = state.failures.length;
    const series = state.heatsEnumerated || perdues;
    const pluriel = perdues > 1;
    toast.warning("Import partiel", {
      description: `${perdues} série${pluriel ? "s" : ""} sur ${series} n'${pluriel ? "ont" : "a"} pas pu être importée${pluriel ? "s" : ""}. ${bilan}`,
      action,
    });
    return;
  }
  toast.success("Import terminé", { description: bilan, action });
}
