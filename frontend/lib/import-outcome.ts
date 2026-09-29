import type { ImportState } from "@/hooks/useImportStream";
import { formatAttente } from "@/lib/utils/format";

/**
 * Lecture de l'issue d'un import, partagée par l'écran d'import et le toast
 * global de `ImportStreamProvider` (#1062) : les deux disent la même chose,
 * avec les mêmes mots.
 */

/** Trois causes, trois gestes (#491, ACT-2). `errorStatus` vaut `null` quand
 *  le flux s'est ouvert avant d'annoncer l'échec : c'est le **seul** cas où la
 *  page est en cause, donc le seul qui vaille une saisie manuelle et un
 *  signalement au back-office. */
export type MotifEchec = "plafond" | "service" | "lecture";

export function motifEchec(state: Pick<ImportState, "phase" | "errorStatus">): MotifEchec | null {
  if (state.phase !== "error") return null;
  if (state.errorStatus === 429) return "plafond";
  if (state.errorStatus === 0 || (state.errorStatus !== null && state.errorStatus >= 500)) return "service";
  return "lecture";
}

/** Un import qui ramène des séries en échec n'est pas un import réussi (#491, ACT-3). */
export function estPartiel(state: Pick<ImportState, "phase" | "failures">): boolean {
  return state.phase === "done" && state.failures.length > 0;
}

/** `!partiel` en tête : un import tout en cache **plus** une série perdue ne
 *  doit pas escamoter la liste des manques derrière « déjà enregistrés ». */
export function estDoublon(
  state: Pick<ImportState, "phase" | "failures" | "cached" | "imported" | "updated" | "skipped">,
): boolean {
  return (
    state.phase === "done" &&
    !estPartiel(state) &&
    (state.cached || (state.imported === 0 && state.updated === 0 && state.skipped > 0))
  );
}

/** « N résultats ajoutés · M mis à jour · K déjà présents », les libellés du bilan à l'écran. */
export function bilanResultats(imported: number, updated: number, skipped: number): string {
  const pluriel = (n: number) => (n > 1 ? "s" : "");
  return `${imported} résultat${pluriel(imported)} ajouté${pluriel(imported)} · ${updated} mis à jour · ${skipped} déjà présent${pluriel(skipped)}`;
}

/** Titre et phrase d'un échec, construits sur sa **cause**, jamais sur le
 *  message d'exception : une coupure réseau y porte le texte anglais du
 *  navigateur (« Failed to fetch »). Seule la lecture impossible reprend le
 *  message du flux, rédigé en français par le scraper pour dire quoi corriger. */
export function echecImport(
  state: Pick<ImportState, "phase" | "errorStatus" | "error">,
  attenteRestante: number,
): { titre: string; description: string } | null {
  const motif = motifEchec(state);
  if (motif === "plafond")
    return {
      titre: "Trop d'imports dans l'heure",
      description:
        attenteRestante > 0
          ? `Réessayez dans ${formatAttente(attenteRestante)}.`
          : "Vous pouvez réessayer maintenant.",
    };
  if (motif === "service")
    return {
      titre: "Le service n'a pas répondu",
      description: "Connexion interrompue ou service momentanément indisponible. L'adresse collée n'est pas en cause.",
    };
  if (motif === "lecture")
    return {
      titre: "Impossible d'importer automatiquement",
      description: state.error ?? "Le lien fourni n'a pas pu être lu.",
    };
  return null;
}
