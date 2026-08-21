"use client";
import { useState } from "react";
import Link from "next/link";
import { Progress } from "@/components/ui/progress";
import { AnnonceStatut } from "@/components/tcn";
import { eventTypeLabel } from "@/lib/constants";
import type { ImportState } from "@/hooks/useImportStream";

/** Quart de progression (0-4) : jalon de l'annonce en phase `saving`. */
function quart(state: ImportState): number {
  const pct = state.total > 0 ? Math.round((state.progress / state.total) * 100) : 0;
  return Math.floor(pct / 25);
}

/**
 * Jalon courant de l'import — sert de clé de déduplication (#477) : le flux
 * SSE émet un message par participant enregistré, et annoncer chacun
 * spammerait un lecteur d'écran. On ne réannonce qu'au changement de heat
 * (scraping), de quart de progression (saving), ou de phase.
 */
function jalon(state: ImportState): string {
  if (state.phase === "scraping") return `scraping:${state.heatIndex}`;
  if (state.phase === "saving") return `saving:${quart(state)}`;
  return state.phase;
}

function texteJalon(state: ImportState): string {
  if (state.phase === "scraping") {
    if (state.heatsScrapingTotal > 0) {
      return `Import en cours : heat ${state.heatIndex} sur ${state.heatsScrapingTotal}${state.heatLabel ? ` (${state.heatLabel})` : ""}.`;
    }
    return state.message || "Import en cours : récupération des participants.";
  }
  if (state.phase === "saving") {
    const pct = state.total > 0 ? Math.round((state.progress / state.total) * 100) : 0;
    return `Enregistrement en cours : ${state.progress} sur ${state.total} (${pct} %).`;
  }
  if (state.phase === "done") {
    return state.cached
      ? `Import terminé, déjà à jour (${state.skipped} participants en cache).`
      : `Import terminé : ${state.imported} ajoutés, ${state.updated} mis à jour, ${state.skipped} ignorés.`;
  }
  return state.error || "Erreur lors de l'import.";
}

export function ImportProgress({ state }: { state: ImportState }) {
  // Ajustement pendant le rendu (patron déjà en place dans `RaceFinishers`) :
  // ne recalcule le texte annoncé qu'au changement de jalon, jamais à chaque
  // re-rendu déclenché par un message SSE dans le même quart.
  const [dernierJalon, setDernierJalon] = useState<string | null>(null);
  const [texteAnnonce, setTexteAnnonce] = useState("");

  if (state.phase === "idle") return null;

  const jalonCourant = jalon(state);
  if (jalonCourant !== dernierJalon) {
    setDernierJalon(jalonCourant);
    setTexteAnnonce(texteJalon(state));
  }

  const pct = state.total > 0 ? Math.round((state.progress / state.total) * 100) : 0;

  return (
    <div className="space-y-2 rounded-md border p-4 text-sm">
      <AnnonceStatut texte={texteAnnonce} busy={state.phase === "scraping" || state.phase === "saving"} />
      {state.phase === "scraping" && <p>{state.message || "Récupération des participants…"}</p>}
      {state.phase === "saving" && (
        <>
          <div className="flex justify-between">
            <span>Import en cours… {state.progress}/{state.total}</span>
            <span className="text-[var(--tcn-text-faint)]">
              {state.imported} ajoutés · {state.updated} mis à jour · {state.skipped} ignorés
            </span>
          </div>
          <Progress value={pct} />
        </>
      )}
      {state.phase === "done" && (
        <>
          <p className="font-medium text-success">
            {state.cached
              ? `Déjà à jour (${state.skipped} participants en cache).`
              : `Import terminé : ${state.imported} ajoutés, ${state.updated} mis à jour, ${state.skipped} ignorés.`}
          </p>
          {state.courses.length > 0 && (
            <div className="space-y-1 pt-2">
              <p className="text-[var(--tcn-text-faint)]">
                {state.courses.length === 1 ? "1 épreuve importée :" : `${state.courses.length} épreuves importées :`}
              </p>
              <ul className="space-y-1">
                {state.courses.map((c) => (
                  <li key={c.id}>
                    <Link href={`/courses/${c.id}`} className="underline hover:no-underline">
                      {c.name}
                    </Link>
                    <span className="ml-2 text-xs text-[var(--tcn-text-faint)]">{eventTypeLabel(c.event_type)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {state.failures.length > 0 && (
            <div className="space-y-1 pt-2">
              <p className="font-medium text-destructive">
                {state.failures.length === 1
                  ? "1 série n'a pas pu être importée :"
                  : `${state.failures.length} séries n'ont pas pu être importées :`}
              </p>
              <ul className="space-y-1 text-xs text-destructive">
                {state.failures.map((f, i) => (
                  <li key={`${f.heat_slug}-${i}`}>{f.reason}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {state.phase === "error" && (
        <p className="text-destructive">{state.error || "Erreur lors de l'import."}</p>
      )}
    </div>
  );
}
