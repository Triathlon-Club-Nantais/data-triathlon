"use client";
import { Fragment, useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useBatchReport, useBatchRuns } from "@/lib/queries/batches";
import { formatDate } from "@/lib/utils/date";
import type { BatchRun } from "@/lib/types";

/** Le workflow borne à 120 minutes ; au-delà, quelque chose est coincé. */
const TROP_LONG_MS = 2 * 60 * 60 * 1000;

/**
 * L'heure courante, rafraîchie chaque minute.
 *
 * Un `Date.now()` en plein rendu est impur — React l'interdit, et le lint le
 * refuse. Passer par un état a un second mérite : le signalement des deux
 * heures apparaît **tout seul**, sans attendre le prochain rechargement de la
 * liste.
 */
function useMaintenant(): number {
  // Initialiseur paresseux : `Date.now()` y est appelé une fois, hors du corps
  // de rendu — la forme que la règle de pureté laisse passer.
  const [maintenant, setMaintenant] = useState(() => Date.now());
  useEffect(() => {
    const minuterie = setInterval(() => setMaintenant(Date.now()), 60_000);
    return () => clearInterval(minuterie);
  }, []);
  return maintenant;
}

const ETATS: Record<BatchRun["state"], string> = {
  pending: "En attente",
  running: "En cours",
  completed: "Terminé",
};

const ISSUES: Record<NonNullable<BatchRun["outcome"]>, string> = {
  success: "Réussi",
  failure: "Échec",
  cancelled: "Annulé",
};

const ORIGINES: Record<BatchRun["triggered_by"], string> = {
  ui: "Interface",
  schedule: "Planifié",
  manual: "Manuel",
};

/** Le français d'affichage est produit ici, jamais par l'API (Principe I). */
function libelleEtat(run: BatchRun): string {
  return run.outcome ? ISSUES[run.outcome] : ETATS[run.state];
}

function duree(secondes: number | null): string {
  if (secondes === null) return "—";
  const minutes = Math.floor(secondes / 60);
  return minutes < 1 ? `${secondes} s` : `${minutes} min`;
}

function BilanDuLancement({ runId }: { runId: number }) {
  const { data, isLoading, error } = useBatchReport(runId);

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  // Le message du serveur, tel quel : il distingue « pas encore de bilan »
  // (404) de « bilan expiré » (410), et cette nuance ne se redevine pas ici.
  if (error) return <p className="text-sm text-destructive">{error.message}</p>;
  if (!data) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Deux unités, nommées — le rapport texte les nomme, l'écran aussi.
          « 117 traitées » sans unité se lit en participants et fait paraître
          l'import ridicule. */}
      <div data-testid="compteurs-epreuves" className="text-sm">
        <div className="font-bold">Épreuves</div>
        <div className="text-[var(--tcn-text-faint)]">
          {data.unique_supported} ciblées · {data.processed} traitées ·{" "}
          {data.errors} en erreur
        </div>
      </div>
      <div data-testid="compteurs-participants" className="text-sm">
        <div className="font-bold">Participants</div>
        <div className="text-[var(--tcn-text-faint)]">
          {data.imported} importés · {data.updated} mis à jour · {data.skipped}{" "}
          inchangés
        </div>
      </div>
      {data.failures.length > 0 && (
        <ul className="sm:col-span-2 space-y-1 text-sm text-[var(--tcn-text-faint)]">
          {data.failures.map((echec) => (
            <li key={echec.url}>
              {echec.label} — {echec.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BatchRunList() {
  const { data, isLoading, error } = useBatchRuns();
  const [ouvert, setOuvert] = useState<number | null>(null);
  const maintenant = useMaintenant();

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  // Un refus n'est pas une liste vide : « aucun lancement » se lirait comme une
  // information, alors qu'elle est seulement indisponible.
  if (error)
    return (
      <EmptyState title="Lancements indisponibles" description={error.message} />
    );
  if (!data?.length)
    return (
      <EmptyState
        title="Aucun lancement"
        description="Les batches lancés depuis cet écran apparaîtront ici."
      />
    );

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Lancement</TableHead>
            <TableHead>État</TableHead>
            <TableHead>Origine</TableHead>
            <TableHead>Démarré</TableHead>
            <TableHead>Durée</TableHead>
            <TableHead>Bilan</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((run) => {
            const coince =
              run.state === "running" &&
              maintenant - new Date(run.started_at).getTime() > TROP_LONG_MS;
            return (
              <Fragment key={run.id}>
                <TableRow>
                  <TableCell>{run.label}</TableCell>
                  <TableCell>
                    <Badge>{libelleEtat(run)}</Badge>
                    {coince && (
                      <p className="mt-1 text-xs text-[var(--tcn-text-faint)]">
                        En cours depuis plus de deux heures.{" "}
                        <a
                          className="underline"
                          href={run.external_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Annuler l&apos;exécution
                        </a>
                      </p>
                    )}
                  </TableCell>
                  <TableCell>{ORIGINES[run.triggered_by]}</TableCell>
                  <TableCell>{formatDate(run.started_at)}</TableCell>
                  <TableCell>{duree(run.duration_s)}</TableCell>
                  <TableCell>
                    {run.report_available ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setOuvert(ouvert === run.id ? null : run.id)
                        }
                      >
                        Bilan
                      </Button>
                    ) : (
                      <span className="text-sm text-[var(--tcn-text-faint)]">
                        Aucun bilan
                      </span>
                    )}
                  </TableCell>
                </TableRow>
                {ouvert === run.id && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <BilanDuLancement runId={run.id} />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
