"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useCourseMergeImpact, useMergeCourses } from "@/lib/queries/admin";
import { eventTypeLabel } from "@/lib/constants";
import { providerLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils/date";
import { motCompte, plural } from "@/lib/utils/format";
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
      <span className="block font-medium">
        Garder n° {course.id} · {providerLabel(course.provider)}
      </span>
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
 * La cible proposée d'office, ou `null` quand rien ne la désigne (#1199).
 *
 * La fusion garde les lignes de la cible : garder une republication sans club
 * efface les résultats TCN de l'autre (Couëron 2025, runnerbreizh 718 gardée,
 * 28 résultats TCN de timepulse perdus). Celle qui en porte le plus l'emporte ;
 * à égalité, runnerbreizh, qui ne publie jamais de club, passe en dernier.
 */
function cibleSuggeree(a: DuplicateCourse, b: DuplicateCourse): number | null {
  if (a.tcn_count !== b.tcn_count) return a.tcn_count > b.tcn_count ? a.id : b.id;
  if ((a.provider === "runnerbreizh") !== (b.provider === "runnerbreizh")) {
    return a.provider === "runnerbreizh" ? b.id : a.id;
  }
  return null;
}

/**
 * Fusionner deux lignes `Course` qui désignent la même épreuve (#287, #292).
 *
 * **La cible reste un choix** : le nombre de participations peut favoriser la
 * source la moins fiable. Seuls les résultats TCN, ou une source qui ne publie
 * aucun club, désignent une cible proposée d'office (`cibleSuggeree`, #1199) ;
 * l'administrateur peut toujours pointer l'autre carte, et un avertissement le
 * retient quand il s'apprête à perdre des résultats du club.
 *
 * Aperçu chargé **à la sélection** (même patron que `DeleteCourseDialog`),
 * donc dès l'ouverture quand une cible est proposée d'office : sans cible, rien
 * n'est chiffré.
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
  const [cibleId, setCibleId] = useState<number | null>(() => cibleSuggeree(courseA, courseB));
  const cible = cibleId === null ? null : cibleId === courseA.id ? courseA : courseB;
  const absorbee = cibleId === null ? null : cibleId === courseA.id ? courseB : courseA;

  const impact = useCourseMergeImpact(cibleId, absorbee?.id ?? null);
  const fusion = useMergeCourses();

  async function confirmer() {
    if (cibleId === null || absorbee === null) return;
    try {
      const resultat = await fusion.mutateAsync({ courseId: cibleId, absorbedId: absorbee.id });
      const p = resultat.participations_deleted;
      const a = resultat.athletes_purged;
      toast.success(
        `« ${absorbee.name} » a été fusionnée dans la source conservée — ` +
          `${motCompte(p, "résultat")} sans correspondance ${plural(p, "a", "ont")} disparu, ` +
          `${motCompte(a, "fiche")} athlète ${plural(a, "purgée")}.`,
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
      titre="Fusionner ces deux épreuves ?"
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

      {cible && absorbee && absorbee.tcn_count > cible.tcn_count && (
        <p role="alert" className="text-sm font-medium text-destructive">
          L&apos;épreuve supprimée porte {motCompte(absorbee.tcn_count, "résultat")} TCN, celle
          conservée {cible.tcn_count === 0 ? "aucun" : `seulement ${cible.tcn_count}`} : la fusion
          garde les lignes de la conservée, et ces résultats ne compteront plus pour le club.
          Gardez plutôt l&apos;autre.
        </p>
      )}

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
            <strong>{impact.data.participations_without_match}</strong>{" "}
            {plural(impact.data.participations_without_match, "résultat")} de l&apos;épreuve
            absorbée n&apos;{plural(impact.data.participations_without_match, "a", "ont")} pas
            d&apos;équivalent côté cible et{" "}
            {plural(impact.data.participations_without_match, "disparaîtra", "disparaîtront")}{" "}
            (dont <strong>{impact.data.tcn_participations_without_match}</strong> du TCN).
          </li>
          <li>
            <strong>{impact.data.athletes_orphaned}</strong>{" "}
            {plural(impact.data.athletes_orphaned, "fiche")} athlète ne{" "}
            {plural(impact.data.athletes_orphaned, "conservera", "conserveront")} plus aucun
            résultat et {plural(impact.data.athletes_orphaned, "sera retirée", "seront retirées")}.
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
