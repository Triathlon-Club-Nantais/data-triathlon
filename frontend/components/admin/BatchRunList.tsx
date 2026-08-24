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
import { useSession } from "@/lib/queries/auth";
import { formatDateTime } from "@/lib/utils/date";
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

/**
 * Un couple aplat/encre par issue. En aplat primaire, « Réussi », « Échec » et
 * « Annulé » sortaient identiques à l'œil (ADM-3) ; l'orange reste au seul
 * état qui bouge encore.
 *
 * Les variantes génériques de `Badge` ne suffisaient pas : `destructive` pose
 * `--tcn-danger` sur son propre aplat à 10 %, soit 3,25:1 sous 12 px — en
 * dessous des 4,5:1 de WCAG 1.4.3 pour le seul mot qui dit qu'un batch a
 * échoué. Les couples sémantiques du thème passent (4,89:1 et 7,25:1), et
 * `secondary`/`outline` ne se distinguaient de toute façon pas du fond de la
 * carte (1,11:1 et 1,22:1).
 */
const APLATS: Record<NonNullable<BatchRun["outcome"]>, string> = {
  success: "bg-[var(--tcn-success-bg)] text-[var(--tcn-success-text)]",
  failure: "bg-[var(--tcn-danger-bg)] text-[var(--tcn-danger-text)]",
  cancelled: "bg-[var(--tcn-fill)] text-[var(--tcn-text-faint)]",
};

/**
 * Anneau de focus opaque, la norme du dépôt (`globals.css`, `.tcn-btn`) :
 * l'anneau UA hérité, `outline-ring/50`, ne vaut que 1,93:1 sur le blanc de la
 * carte, contre les 3:1 de WCAG 1.4.11. `-my-1 py-1` porte la cible de 16 à
 * 24 px sans déplacer la mise en page (SC 2.5.8), comme le fait déjà le lien
 * de retour de `PageHeader`.
 */
const LIEN =
  "-my-1 inline-block py-1 text-xs underline text-[var(--tcn-text-faint)] " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-[var(--tcn-orange)]";

/** « il y a 3 minutes », « il y a 2 heures », « il y a 4 jours ». */
const RELATIF = new Intl.RelativeTimeFormat("fr-FR", { numeric: "auto" });

function ilYA(millisecondes: number): string {
  // `format(NaN)` **lève** — un `started_at` illisible emporterait alors tout
  // le tableau, les lignes saines comprises. Et un horodatage dans le futur
  // (horloge serveur en avance) rendrait « dans 3 minutes » sur un départ.
  if (!Number.isFinite(millisecondes)) return "";
  const minutes = Math.max(0, Math.floor(millisecondes / 60_000));
  // « cette minute-ci », ce que rend `numeric: "auto"` à zéro, se lit mal dans
  // une colonne « Démarré » — et c'est l'état juste après le clic.
  if (minutes === 0) return "à l'instant";
  if (minutes < 60) return RELATIF.format(-minutes, "minute");
  // Un temps écoulé se plancherise : arrondi, 40 h sorti en « avant-hier »
  // donne un mot de calendrier faux.
  const heures = Math.floor(minutes / 60);
  if (heures < 24) return RELATIF.format(-heures, "hour");
  return RELATIF.format(-Math.floor(heures / 24), "day");
}

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
  const session = useSession();
  const peutLire = session.data?.permissions.includes("batch:read") ?? false;
  // L'écran est annoncé sur `batch:run` : cette liste-ci est la part que ce
  // pouvoir-là n'ouvre pas. Sans la garde, elle partait en 403 et s'affichait en
  // « Lancements indisponibles » avec le message serveur brut — un état d'erreur
  // comme rendu par défaut d'un visiteur légitime (ADM-2).
  const { data, isLoading, error } = useBatchRuns(peutLire);
  const [ouvert, setOuvert] = useState<number | null>(null);
  const maintenant = useMaintenant();

  // Une session illisible n'est pas une session sans pouvoirs : `useSession` ne
  // réessaie pas, et dire « demande le pouvoir » sur une panne accuse à tort.
  // Son message ne sort pas : le repli d'`ApiError` est `statusText`, en
  // anglais — contrairement à celui de la liste elle-même, écrit en français
  // par le backend et qui distingue 404, 410 et 503.
  if (session.error)
    return (
      <EmptyState
        title="Lancements indisponibles"
        description="Vos pouvoirs n'ont pas pu être lus. Rechargez la page."
      />
    );
  // La conséquence — le lancement à l'aveugle, et le 409 qui l'arrête — est
  // dite une seule fois, par `BatchLauncher`. Ici, le seul fait.
  if (!peutLire && !session.isPending)
    return (
      <EmptyState
        title="Lancements non affichés"
        description="Demande le pouvoir « Consulter les batches »."
      />
    );
  if (isLoading || session.isPending) return <Skeleton className="h-40 w-full" />;
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
            const ecoule = maintenant - new Date(run.started_at).getTime();
            const coince = run.state === "running" && ecoule > TROP_LONG_MS;
            // `duration_s` reste nul tant que l'exécution tourne : sans le
            // temps écoulé, la colonne disait « — » pendant deux heures.
            const secondes =
              run.duration_s ??
              (run.state === "completed" || !Number.isFinite(ecoule)
                ? null
                : Math.max(0, Math.floor(ecoule / 1000)));
            return (
              <Fragment key={run.id}>
                <TableRow>
                  <TableCell>
                    <div>{run.label}</div>
                    {/* En permanence, pas seulement quand ça coince : c'est le
                        seul endroit qui dit où le batch tourne réellement. Le
                        nom accessible porte le libellé : sans lui, la liste de
                        liens d'un lecteur d'écran répète N fois le même mot
                        pour N destinations (SC 2.4.4). */}
                    <a
                      className={LIEN}
                      aria-label={`Voir l'exécution ${run.label} (nouvel onglet)`}
                      href={run.external_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Voir l&apos;exécution
                    </a>
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={run.outcome ? APLATS[run.outcome] : undefined}
                    >
                      {libelleEtat(run)}
                    </Badge>
                    {coince && (
                      // Pas de second lien : il pointait `external_url`, la
                      // même page que « Voir l'exécution » une colonne plus
                      // tôt, sous un nom qui promettait une annulation qu'il
                      // n'exécutait pas.
                      <p className="mt-1 text-xs text-[var(--tcn-text-faint)]">
                        En cours depuis plus de deux heures. Vous pouvez
                        l&apos;annuler depuis la page de l&apos;exécution.
                      </p>
                    )}
                  </TableCell>
                  <TableCell>{ORIGINES[run.triggered_by]}</TableCell>
                  <TableCell data-testid={`demarrage-${run.id}`}>
                    <div>{formatDateTime(run.started_at)}</div>
                    <div className="text-xs text-[var(--tcn-text-faint)]">
                      {ilYA(ecoule)}
                    </div>
                  </TableCell>
                  <TableCell data-testid={`duree-${run.id}`}>
                    {duree(secondes)}
                  </TableCell>
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
