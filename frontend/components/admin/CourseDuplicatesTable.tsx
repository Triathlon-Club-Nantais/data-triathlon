"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { useCourseDuplicates, useIgnoreCourseDuplicate } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { eventTypeLabel, providerLabel } from "@/lib/constants";
import { formatDate } from "@/lib/utils/date";
import type { DuplicateCandidate, DuplicateCourse } from "@/lib/types";
import { MergeCoursesDialog } from "./MergeCoursesDialog";

const REFUS = { sujet: "doublons suspects", action: "consulter les doublons suspects" };

/**
 * Une correction d'identité résout la cause, la fusion n'efface que le
 * symptôme (#292) : `same_source_url` signale deux scrapes de la **même**
 * URL classées différemment (#294), pas deux chronométreurs concurrents. Sans
 * #294, une fusion se déferait au prochain re-scrape qui reproduit la
 * classification d'origine.
 */
function NoteRaison({ reason }: { reason: DuplicateCandidate["reason"] }) {
  if (reason !== "same_source_url") return null;
  return (
    <p className="text-[var(--tcn-text-faint)] text-xs">
      Ces deux lignes viennent de la même URL : une correction du type d&apos;épreuve
      (bouton « Corriger » du catalogue) résout la cause. La fusion n&apos;efface que
      le symptôme — elle se déferait au prochain re-scrape.
    </p>
  );
}

function LigneEpreuve({ course }: { course: DuplicateCourse }) {
  return (
    <div className="text-sm">
      <span className="font-medium">{providerLabel(course.provider)}</span>{" · "}
      {course.name}
      {course.event_date ? ` · ${formatDate(course.event_date)}` : ""} ·{" "}
      {eventTypeLabel(course.event_type)} · {course.total} résultat{course.total > 1 ? "s" : ""}
      {course.tcn_count > 0 ? ` (dont ${course.tcn_count} TCN)` : ""}
    </div>
  );
}

function CandidatCard({
  candidate,
  peutFusionner,
  peutIgnorer,
}: {
  candidate: DuplicateCandidate;
  peutFusionner: boolean;
  peutIgnorer: boolean;
}) {
  const [fusionOuverte, setFusionOuverte] = useState(false);
  const [courseA, courseB] = candidate.courses;
  const ecarter = useIgnoreCourseDuplicate();
  const confirmer = useDangerConfirm();

  /**
   * Geste neutre, jamais destructif (#754) : écarter ne supprime aucune
   * donnée, il retire une suggestion. Confirmé malgré tout (revue UI/UX de fin
   * de branche) : contrairement à « Marquer comme traité » de
   * `PendingProvidersTable` — reversible, un signalement à nouveau reçu
   * recrée la ligne —, aucun écran « paires écartées » n'existe dans ce ticket
   * pour revenir sur un clic. `useDangerConfirm({ actionNeutre: true })`, sur
   * le patron de `basculerLeStatut` de `RolePermissionsEditor` : confirmé dans
   * les deux sens, mais sans la couleur destructive — le geste ne ferme aucun
   * accès et ne détruit aucune donnée (#499), il n'invente pas une troisième
   * catégorie de gravité.
   */
  async function ecarterLaPaire() {
    if (
      !(await confirmer({
        titre: "Écarter cette paire ?",
        description:
          "Elle ne reviendra plus dans cette liste : ce n'est pas un doublon supprimé, seulement une suggestion écartée — aucune donnée n'est détruite.",
        libelleAction: "Écarter",
        actionNeutre: true,
      }))
    ) {
      return;
    }
    try {
      await ecarter.mutateAsync({ courseIdA: courseA.id, courseIdB: courseB.id });
      toast.success("Paire écartée : elle ne reviendra plus dans cette liste.");
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Badge variant="secondary">{candidate.reason_label}</Badge>
          <div className="flex gap-2">
            {peutIgnorer && (
              <Button
                size="sm"
                variant="outline"
                className="min-h-11"
                onClick={ecarterLaPaire}
                disabled={ecarter.isPending}
              >
                {ecarter.isPending ? "Mise à l'écart…" : "Écarter"}
              </Button>
            )}
            {peutFusionner && (
              <Button
                size="sm"
                variant="destructive"
                className="min-h-11"
                onClick={() => setFusionOuverte(true)}
              >
                Fusionner
              </Button>
            )}
          </div>
        </div>
        <div className="space-y-1">
          <LigneEpreuve course={courseA} />
          <LigneEpreuve course={courseB} />
        </div>
        <NoteRaison reason={candidate.reason} />
      </CardContent>

      {fusionOuverte && (
        <MergeCoursesDialog
          courseA={courseA}
          courseB={courseB}
          open={fusionOuverte}
          onOpenChange={setFusionOuverte}
        />
      )}
    </Card>
  );
}

/**
 * Doublons suspects entre épreuves (#288), avec fusion manuelle (#287, #292)
 * et mise à l'écart d'une paire (#754).
 *
 * Lecture réservée (`courses:sources`) : sans droit, `data` reste `undefined`
 * et un écran qui ne lit que ça dirait « aucun doublon », un mensonge — d'où
 * `messageDeRefus`, comme `PendingProvidersTable`.
 *
 * La fusion exige en plus `courses:delete` (deux `Depends` côté backend) :
 * un porteur du seul `courses:sources` voit la liste mais aucun bouton
 * « Fusionner » — lui en proposer un finirait systématiquement en 403.
 *
 * Écarter, lui, ne demande que `courses:sources` (#754) — le même pouvoir que
 * la lecture, puisque le geste n'est qu'un arbitrage, jamais une suppression.
 * Quiconque voit cette liste peut donc toujours écarter une paire ; le test
 * du pouvoir reste posé explicitement, patron des « Gardes d'écriture du
 * back-office » (`frontend/AGENTS.md`), pour rester correct si la garde de
 * lecture change un jour sans que ce fichier soit relu.
 */
export function CourseDuplicatesTable() {
  const { data, isLoading, error } = useCourseDuplicates();
  const session = useSession();
  const peutFusionner = session.data?.permissions.includes("courses:delete") ?? false;
  const peutIgnorer = session.data?.permissions.includes("courses:sources") ?? false;

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.candidates.length === 0) {
    return (
      <EmptyState
        title="Aucun doublon suspect"
        description="Aucune paire d'épreuves ne partage une URL, un identifiant d'événement ou un nom proche à la même date."
      />
    );
  }

  return (
    <div className="space-y-3">
      {data.candidates.map((candidate) => (
        <CandidatCard
          key={`${candidate.reason}-${candidate.courses[0].id}-${candidate.courses[1].id}`}
          candidate={candidate}
          peutFusionner={peutFusionner}
          peutIgnorer={peutIgnorer}
        />
      ))}
    </div>
  );
}
