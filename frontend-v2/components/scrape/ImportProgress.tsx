"use client";
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
            <span className="text-muted-foreground">
              {state.imported} importés · {state.skipped} ignorés
            </span>
          </div>
          <Progress value={pct} />
        </>
      )}
      {state.phase === "done" && (
        <p className="font-medium text-success">
          {state.cached
            ? `Déjà à jour (${state.skipped} participants en cache).`
            : `Import terminé : ${state.imported} ajoutés, ${state.skipped} ignorés.`}
        </p>
      )}
      {state.phase === "error" && (
        <p className="text-destructive">{state.error || "Erreur lors de l'import."}</p>
      )}
    </div>
  );
}
