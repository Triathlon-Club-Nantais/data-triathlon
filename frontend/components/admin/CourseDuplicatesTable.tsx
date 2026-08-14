"use client";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useCourseDuplicates } from "@/lib/queries/admin";
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
}: {
  candidate: DuplicateCandidate;
  peutFusionner: boolean;
}) {
  const [fusionOuverte, setFusionOuverte] = useState(false);
  const [courseA, courseB] = candidate.courses;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <Badge variant="secondary">{candidate.reason_label}</Badge>
          {peutFusionner && (
            <Button size="sm" variant="outline" onClick={() => setFusionOuverte(true)}>
              Fusionner
            </Button>
          )}
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
 * Doublons suspects entre épreuves (#288), avec fusion manuelle (#287, #292).
 *
 * Lecture réservée (`courses:sources`) : sans droit, `data` reste `undefined`
 * et un écran qui ne lit que ça dirait « aucun doublon », un mensonge — d'où
 * `messageDeRefus`, comme `PendingProvidersTable`.
 *
 * La fusion exige en plus `courses:delete` (deux `Depends` côté backend) :
 * un porteur du seul `courses:sources` voit la liste mais aucun bouton
 * « Fusionner » — lui en proposer un finirait systématiquement en 403.
 */
export function CourseDuplicatesTable() {
  const { data, isLoading, error } = useCourseDuplicates();
  const session = useSession();
  const peutFusionner = session.data?.permissions.includes("courses:delete") ?? false;

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
        />
      ))}
    </div>
  );
}
