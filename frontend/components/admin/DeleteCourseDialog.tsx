"use client";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useCourseDeletionImpact, useDeleteCourse } from "@/lib/queries/admin";
import type { CourseBrief } from "@/lib/types";

/**
 * La confirmation d'une suppression d'épreuve (#117, FR-017).
 *
 * **Elle annonce l'ampleur réelle, pas seulement les résultats.** Supprimer une
 * épreuve emporte aussi les fiches coureur qui n'ont couru qu'elle (FR-022) :
 * taire ce nombre reviendrait à sous-déclarer un geste sans retour en arrière.
 * C'est pourquoi l'ouverture chiffre l'impact côté serveur avant de proposer
 * quoi que ce soit.
 *
 * **Aucun bouton d'annulation**, et ce n'est pas un oubli (FR-018) : rien ne
 * restaure une épreuve supprimée. Ce qui reste du geste est son entrée au
 * journal d'audit.
 *
 * Passé sur `DangerConfirm` (#499) : la coquille, les libellés et la place du
 * bouton de renoncement sont désormais les mêmes que pour tous les autres
 * gestes destructifs de l'administration.
 */
export function DeleteCourseDialog({
  course,
  open,
  onOpenChange,
}: {
  course: CourseBrief;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const impact = useCourseDeletionImpact(open ? course.id : null);
  const suppression = useDeleteCourse();

  async function confirmer() {
    try {
      await suppression.mutateAsync(course.id);
      toast.success(`« ${course.name} » a été supprimée.`);
      onOpenChange(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <DangerConfirm
      open={open}
      onOpenChange={onOpenChange}
      titre={`Supprimer « ${course.name} » ?`}
      description={
        <>
          Cette action est <strong>irréversible</strong>. Elle restera tracée dans le
          journal d&apos;administration, mais rien ne permettra de revenir en arrière.
        </>
      }
      actionBloquee={!impact.data}
      enAttente={suppression.isPending}
      onConfirm={confirmer}
    >
      {impact.isLoading && <Skeleton className="h-16 w-full" />}

      {impact.error && (
        <p className="text-sm text-destructive">
          L&apos;ampleur de la suppression n&apos;a pas pu être chiffrée. Par prudence,
          la suppression n&apos;est pas activée — réessayez plus tard.
        </p>
      )}

      {impact.data && (
        <ul className="space-y-1 text-sm">
          <li>
            <strong>{impact.data.participations}</strong> résultat
            {impact.data.participations === 1 ? " sera détruit" : "s seront détruits"}.
          </li>
          <li>
            <strong>{impact.data.athletes}</strong> fiche
            {impact.data.athletes === 1
              ? " coureur ne conservera plus aucun résultat et sera retirée"
              : "s coureur ne conserveront plus aucun résultat et seront retirées"}
            .
          </li>
        </ul>
      )}
    </DangerConfirm>
  );
}
