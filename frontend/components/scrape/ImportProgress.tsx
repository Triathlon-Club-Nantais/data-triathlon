"use client";
import Link from "next/link";
import { Progress } from "@/components/ui/progress";
import type { ImportState } from "@/hooks/useImportStream";

export function ImportProgress({ state }: { state: ImportState }) {
  if (state.phase === "idle") return null;

  const pct = state.total > 0 ? Math.round((state.progress / state.total) * 100) : 0;

  return (
    <div className="space-y-2 rounded-md border p-4 text-sm">
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
                {state.courses.length === 1 ? "1 course importée :" : `${state.courses.length} courses importées :`}
              </p>
              <ul className="space-y-1">
                {state.courses.map((c) => (
                  <li key={c.id}>
                    <Link href={`/courses/${c.id}`} className="underline hover:no-underline">
                      {c.name}
                    </Link>
                    <span className="ml-2 text-xs text-[var(--tcn-text-faint)]">{c.event_type}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {state.failures.length > 0 && (
            <div className="space-y-1 pt-2">
              <p className="font-medium text-destructive">
                Heats en erreur ({state.failures.length}) :
              </p>
              <ul className="space-y-1 text-xs text-destructive">
                {state.failures.map((f, i) => (
                  <li key={`${f.heat_slug}-${i}`}>
                    <span className="font-mono">{f.heat_slug}</span> — {f.reason}
                  </li>
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
