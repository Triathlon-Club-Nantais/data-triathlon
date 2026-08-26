"use client";
import { useEffect, useState } from "react";
import { scaleLinear } from "d3-scale";
import { Card } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import type { ValidationQueueHistory } from "@/lib/types";

function formatJour(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}

function formatDelai(secondes: number): string {
  const heures = secondes / 3600;
  if (heures < 1) return `${Math.round(secondes / 60)} min`;
  if (heures < 48) return `${Math.round(heures)} h`;
  return `${Math.round(heures / 24)} j`;
}

/**
 * Arriéré de la file de validation dans le temps et délai moyen de
 * résolution (US13, #466). Se fetch elle-même : `/benevoles` n'a pas de
 * rendu serveur sur lequel accrocher cette donnée secondaire (mot de passe
 * partagé, pas de session SSO) — une panne ici reste silencieuse plutôt que
 * de bloquer la file elle-même, qui est l'écran principal.
 */
export function ValidationBacklogChart() {
  const [historique, setHistorique] = useState<ValidationQueueHistory | null>(null);
  const [enErreur, setEnErreur] = useState(false);

  useEffect(() => {
    let abandonne = false;
    apiClient
      .getValidationQueueHistory()
      .then((recu) => {
        if (!abandonne) setHistorique(recu);
      })
      .catch(() => {
        if (!abandonne) setEnErreur(true);
      });
    return () => {
      abandonne = true;
    };
  }, []);

  if (enErreur || !historique) return null;

  if (historique.backlog_by_day.length === 0) {
    return (
      <Card padding={16}>
        <p style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Pas encore d&apos;historique de résolution : ce graphique se remplit au fil des validations et des rejets.
        </p>
      </Card>
    );
  }

  const points = historique.backlog_by_day.slice(-30);
  const max = Math.max(1, ...points.map((p) => p.pending_count));
  const heightScale = scaleLinear().domain([0, max]).range([0, 100]);
  const summary = points.map((p) => `${formatJour(p.date)} : ${p.pending_count}`).join(", ");

  return (
    <Card padding={16}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--tcn-ink)" }}>Arriéré de la file</span>
        {historique.average_resolution_seconds != null && (
          <span style={{ fontSize: 12, color: "var(--tcn-text-faint)" }}>
            Délai moyen : {formatDelai(historique.average_resolution_seconds)}
          </span>
        )}
      </div>
      <div role="img" aria-label={`Arriéré de la file par jour : ${summary}.`} className="flex h-28 items-end gap-1">
        {points.map((p, index) => {
          const montrerLabel = index === 0 || index === points.length - 1;
          return (
            <div key={p.date} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
              <div
                aria-hidden
                className="w-full rounded-t-sm bg-[color-mix(in_oklch,var(--primary)_70%,transparent)]"
                style={{ height: `${Math.max(4, heightScale(p.pending_count))}%` }}
              />
              {/* Toujours rendu (jamais retiré du DOM) pour réserver sa hauteur —
                  seule sa visibilité change, patron de `MonthlyTrend.tsx`. */}
              <span
                aria-hidden
                className={`micro-label whitespace-nowrap text-[var(--tcn-text-faint)] ${montrerLabel ? "" : "invisible"}`}
              >
                {formatJour(p.date)}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
