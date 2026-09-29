"use client";
import { useCallback, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { captureEvent } from "@/lib/posthog";
import { apiClient } from "@/lib/api/client";
import { formatEventName } from "@/lib/utils/event";
import {
  ImportStreamContext,
  useImportStreamController,
  type ImportState,
} from "@/hooks/useImportStream";
import { bilanResultats, echecImport, estDoublon, estPartiel, motifEchec } from "@/lib/import-outcome";

/** Un seul import à la fois, donc un seul toast de bilan : un identifiant fixe. */
const TOAST_ID = "import-outcome";
const DUREE_SUCCES = 10_000;

/**
 * L'import de résultats, tenu au niveau du layout (#1062). Une navigation
 * interne démonte `TcnScrapeForm` mais ne coupe pas la SSE : l'import va au
 * bout. S'il finit **sans écran attaché**, ce provider fait ce que l'écran
 * aurait fait (signalement du fournisseur sur page illisible, rafraîchissement,
 * télémétrie) et l'annonce par un toast global. Le bilan reste dans l'état tant
 * que ce toast est affiché : revenir sur `/ajouter` le montre en entier, séries
 * perdues comprises. Le verrou « un import à la fois » vit ici aussi.
 */
export function ImportStreamProvider({ children }: { children: ReactNode }) {
  const { state, url, singleHeat, start, cancel, reset } = useImportStreamController();
  const router = useRouter();
  const attaches = useRef(0);
  const etatRef = useRef(state);
  // Vrai tant qu'un bilan annoncé par toast n'a été ni vu à l'écran ni fermé.
  const bilanEnAttente = useRef(false);
  useEffect(() => {
    etatRef.current = state;
  }, [state]);

  const attach = useCallback(() => {
    attaches.current += 1;
    if (bilanEnAttente.current) {
      // Le bilan est désormais à l'écran : le toast n'a plus à le porter.
      bilanEnAttente.current = false;
      toast.dismiss(TOAST_ID);
    }
    return () => {
      attaches.current -= 1;
      // Un bilan déjà vu ne se rejoue pas au retour suivant sur l'écran.
      if (attaches.current === 0 && !etatRef.current.running && !bilanEnAttente.current) reset();
    };
  }, [reset]);

  const phasePrecedente = useRef(state.phase);
  useEffect(() => {
    const avant = phasePrecedente.current;
    phasePrecedente.current = state.phase;
    if (avant === state.phase || (state.phase !== "done" && state.phase !== "error")) return;
    if (attaches.current > 0) return;

    if (motifEchec(state) === "lecture") apiClient.reportPendingProvider(url).catch(() => {});
    if (state.phase === "done" && !estDoublon(state)) router.refresh();

    const fermer = () => {
      if (!bilanEnAttente.current) return;
      bilanEnAttente.current = false;
      if (attaches.current === 0 && !etatRef.current.running) reset();
    };
    bilanEnAttente.current = true;
    annoncer(state, {
      aller: (href) => router.push(href),
      relancer: () => {
        bilanEnAttente.current = false;
        start(url, singleHeat);
        router.push("/ajouter");
      },
      fermer,
    });
  }, [state, url, singleHeat, router, reset, start]);

  // Fermer l'onglet, lui, coupe la SSE à mi-course, où que l'on soit.
  useEffect(() => {
    if (!state.running) return;
    const garde = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", garde);
    return () => window.removeEventListener("beforeunload", garde);
  }, [state.running]);

  const valeur = useMemo(
    () => ({ state, url, singleHeat, start, cancel, reset, attach }),
    [state, url, singleHeat, start, cancel, reset, attach],
  );
  return <ImportStreamContext.Provider value={valeur}>{children}</ImportStreamContext.Provider>;
}

/** « « Triathlon de Nantes » », « 2 épreuves », ou rien sans épreuve. */
function nomDesEpreuves(state: ImportState): string | null {
  if (state.courses.length === 0) return null;
  if (state.courses.length > 1) return `${state.courses.length} épreuves`;
  const [seule] = state.courses;
  return `« ${formatEventName(seule.name, Boolean(seule.is_relay))} »`;
}

function annoncer(
  state: ImportState,
  gestes: { aller: (href: string) => void; relancer: () => void; fermer: () => void },
) {
  const { aller, relancer, fermer } = gestes;
  const persistant = { id: TOAST_ID, duration: Infinity, closeButton: true, onDismiss: fermer, onAutoClose: fermer };

  if (state.phase === "error") {
    captureEvent("results_import_failed", { error_message: state.error ?? "Import impossible" });
    const motif = motifEchec(state);
    const attente = Math.max(0, (state.retryAfter ?? 0) - Math.floor((Date.now() - state.endedAt) / 1000));
    const echec = echecImport(state, attente)!;
    if (motif === "plafond") {
      toast.warning(echec.titre, {
        ...persistant,
        description: echec.description,
        action: { label: "Voir le décompte", onClick: () => aller("/ajouter") },
      });
    } else {
      toast.error(echec.titre, {
        ...persistant,
        description: echec.description,
        action:
          motif === "lecture"
            ? { label: "Saisir à la main", onClick: () => aller("/ajouter") }
            : { label: "Relancer l'import", onClick: relancer },
      });
    }
    return;
  }

  captureEvent("results_import_completed", {
    imported_count: state.imported,
    skipped_count: state.skipped,
    course_count: state.courses.length,
  });
  const nom = nomDesEpreuves(state);
  const [seule] = state.courses;
  const voir =
    state.courses.length > 1
      ? { label: "Voir les épreuves", onClick: () => aller("/ajouter") }
      : seule
        ? { label: "Voir les résultats", onClick: () => aller(`/courses/${seule.id}`) }
        : undefined;
  const bilan = bilanResultats(state.imported, state.updated, state.skipped);

  if (estPartiel(state)) {
    const perdues = state.failures.length;
    const series = state.heatsEnumerated || perdues;
    toast.warning(nom ? `Import partiel : ${nom}` : "Import partiel", {
      ...persistant,
      description: `${perdues} série${perdues > 1 ? "s" : ""} sur ${series} manque${perdues > 1 ? "nt" : ""}. ${bilan}`,
      action: { label: "Voir le bilan", onClick: () => aller("/ajouter") },
    });
    return;
  }
  const passager = { id: TOAST_ID, duration: DUREE_SUCCES, onDismiss: fermer, onAutoClose: fermer, action: voir };
  if (estDoublon(state)) {
    toast.message("Résultats déjà enregistrés", {
      ...passager,
      description: state.courses.length === 1 ? `${nom} était déjà à jour.` : "Ces résultats avaient déjà été ajoutés.",
    });
    return;
  }
  toast.success(nom ? `Résultats enregistrés : ${nom}` : "Résultats enregistrés", {
    ...passager,
    description: bilan,
  });
}
