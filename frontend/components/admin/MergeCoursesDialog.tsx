"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useCourseMergeImpact, useMergeCourses } from "@/lib/queries/admin";
import { eventTypeLabel, providerLabel } from "@/lib/constants";
import { formatDate } from "@/lib/utils/date";
import type { DuplicateCourse } from "@/lib/types";

function CarteEpreuve({
  course,
  choisie,
  onChoisir,
}: {
  course: DuplicateCourse;
  choisie: boolean;
  onChoisir: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onChoisir}
      aria-pressed={choisie}
      className={`w-full rounded-md border p-3 text-left text-sm hover:bg-accent ${
        choisie ? "border-primary bg-accent" : "border-transparent"
      }`}
    >
      <span className="block font-medium">Garder {providerLabel(course.provider)}</span>
      <span className="text-[var(--tcn-text-faint)] block text-xs">
        {course.name}
        {course.event_date ? ` · ${formatDate(course.event_date)}` : ""} ·{" "}
        {eventTypeLabel(course.event_type)} · {course.total} résultat{course.total > 1 ? "s" : ""}
        {course.tcn_count > 0 ? ` (dont ${course.tcn_count} TCN)` : ""}
      </span>
    </button>
  );
}

/**
 * Fusionner deux lignes `Course` qui désignent la même épreuve (#287, #292).
 *
 * **La cible se choisit, elle ne se déduit pas** : rien dans une paire de
 * doublons ne dit laquelle des deux garder — ni l'ordre reçu de l'API, ni le
 * nombre de participations, qui peut favoriser la source la moins fiable.
 * L'administrateur pointe une carte, l'autre devient l'absorbée.
 *
 * Aperçu chargé **à la sélection**, jamais avant (même patron que
 * `DeleteCourseDialog`) : chiffrer une fusion qui n'aura peut-être pas lieu
 * coûterait un aller-retour serveur pour rien.
 *
 * Passée sur `DangerConfirm` (#499) : la fusion détruit la ligne absorbée et
 * ses fiches coureur orphelines, sans retour — même mécanisme que les autres
 * gestes destructifs de l'administration.
 */
export function MergeCoursesDialog({
  courseA,
  courseB,
  open,
  onOpenChange,
}: {
  courseA: DuplicateCourse;
  courseB: DuplicateCourse;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [cibleId, setCibleId] = useState<number | null>(null);
  const absorbee = cibleId === null ? null : cibleId === courseA.id ? courseB : courseA;

  const impact = useCourseMergeImpact(cibleId, absorbee?.id ?? null);
  const fusion = useMergeCourses();

  async function confirmer() {
    if (cibleId === null || absorbee === null) return;
    try {
      await fusion.mutateAsync({ courseId: cibleId, absorbedId: absorbee.id });
      toast.success(
        `« ${absorbee.name} » a été fusionnée dans la source conservée — ses résultats sans correspondance ont disparu.`,
      );
      onOpenChange(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <DangerConfirm
      open={open}
      onOpenChange={onOpenChange}
      titre="Fusionner ces deux lignes ?"
      description={
        <>
          Choisissez l&apos;épreuve à conserver. L&apos;autre est supprimée ; son URL
          devient une source passive de celle conservée, et ses résultats sans
          correspondance disparaissent — la fusion ne re-scrape rien.
        </>
      }
      actionBloquee={!impact.data}
      libelleAction={fusion.isPending ? "Fusion en cours…" : "Fusionner"}
      enAttente={fusion.isPending}
      onConfirm={confirmer}
    >
      <div className="space-y-2">
        <CarteEpreuve course={courseA} choisie={cibleId === courseA.id} onChoisir={() => setCibleId(courseA.id)} />
        <CarteEpreuve course={courseB} choisie={cibleId === courseB.id} onChoisir={() => setCibleId(courseB.id)} />
      </div>

      {cibleId !== null && impact.isLoading && <Skeleton className="h-16 w-full" />}

      {cibleId !== null && impact.error && (
        <p className="text-sm text-destructive">
          L&apos;ampleur de la fusion n&apos;a pas pu être chiffrée. Par prudence, la
          fusion n&apos;est pas activée — réessayez plus tard.
        </p>
      )}

      {impact.data && (
        <ul className="space-y-1 text-sm">
          <li>
            <strong>{impact.data.participations_without_match}</strong> résultat
            {impact.data.participations_without_match > 1 ? "s" : ""} de l&apos;épreuve
            absorbée n&apos;ont pas d&apos;équivalent côté cible et disparaîtront
            (dont <strong>{impact.data.tcn_participations_without_match}</strong> du TCN).
          </li>
          <li>
            <strong>{impact.data.athletes_orphaned}</strong> fiche
            {impact.data.athletes_orphaned > 1 ? "s" : ""} coureur ne conserveront plus
            aucun résultat et {impact.data.athletes_orphaned > 1 ? "seront retirées" : "sera retirée"}.
          </li>
          <li>
            {impact.data.same_source_url
              ? "Aucune source ne sera ajoutée : les deux lignes partagent déjà la même URL."
              : "L'URL de l'épreuve absorbée sera conservée comme source passive de la cible."}
          </li>
        </ul>
      )}
    </DangerConfirm>
  );
}
