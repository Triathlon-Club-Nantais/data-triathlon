"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/tcn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { DeleteCourseDialog } from "@/components/admin/DeleteCourseDialog";
import { EditCourseDialog } from "@/components/admin/EditCourseDialog";
import { MergeCoursesDialog, type MergeableCourse } from "@/components/admin/MergeCoursesDialog";
import { ReliabilityVerdictDialog, type Verdict } from "@/components/admin/ReliabilityVerdictDialog";
import { useDebounce } from "@/hooks/useDebounce";
import { apiClient } from "@/lib/api/client";
import { providerLabel } from "@/lib/labels";
import { useAdminCourses } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import { plural } from "@/lib/utils/format";
import type { CourseBrief } from "@/lib/types";

/**
 * Les gestes d'administration d'une épreuve, depuis sa fiche publique (#1244).
 *
 * Chaque bouton teste **son** pouvoir, celui de la route qu'il appelle : la
 * fusion en exige deux (`courses:sources` et `courses:delete`, deux `Depends`
 * côté backend). Les fenêtres sont celles du back-office, réutilisées telles
 * quelles ; seul leur dénouement change, la page étant rendue côté serveur :
 * `refresh()` après une correction, redirection quand la fiche n'existe plus.
 */
export function CourseAdminActions({
  course,
  total,
  tcnCount,
}: {
  course: CourseBrief;
  total: number;
  tcnCount: number;
}) {
  const router = useRouter();
  const permissions = useHydratedSession().data?.permissions ?? [];
  const canEdit = permissions.includes("courses:write");
  const canDelete = permissions.includes("courses:delete");
  const canReview = permissions.includes("quality:override");
  const canMerge = canDelete && permissions.includes("courses:sources");

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [other, setOther] = useState<MergeableCourse | null>(null);

  if (!canEdit && !canDelete && !canReview) return null;

  const current: MergeableCourse = {
    id: course.id,
    name: course.name,
    event_date: course.event_date,
    event_type: course.event_type,
    is_relay: course.is_relay,
    provider: course.provider,
    source_url: course.source_url,
    total,
    tcn_count: tcnCount,
  };

  async function pickTarget(target: CourseBrief) {
    try {
      // La liste ne porte ni total ni effectif TCN, dont la fusion a besoin pour
      // proposer la cible et avertir d'une perte de résultats du club.
      const summary = await apiClient.getCourseSummary(target.id);
      setOther({ ...target, total: summary.total, tcn_count: summary.tcn_count });
      setSearchOpen(false);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
      {canEdit && (
        <Button size="sm" variant="secondary" onClick={() => setEditOpen(true)}>
          Corriger l&apos;épreuve
        </Button>
      )}
      {canReview && (
        <DropdownMenu>
          <DropdownMenuTrigger className="tcn-btn tcn-btn--sm tcn-btn--secondary">
            Avis de fiabilité
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => setVerdict("fiable")}>Marquer fiable</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setVerdict("douteuse")}>Marquer douteuse</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setVerdict("calcule")}>
              Revenir à l&apos;avis calculé
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      {canMerge && (
        <Button size="sm" variant="destructive" onClick={() => setSearchOpen(true)}>
          Fusionner avec une autre épreuve
        </Button>
      )}
      {canDelete && (
        <Button size="sm" variant="destructive" onClick={() => setDeleteOpen(true)}>
          Supprimer
        </Button>
      )}

      {editOpen && (
        <EditCourseDialog
          course={course}
          open
          onOpenChange={setEditOpen}
          onSaved={() => router.refresh()}
        />
      )}
      <ReliabilityVerdictDialog
        course={course}
        verdict={verdict}
        onOpenChange={(open) => !open && setVerdict(null)}
        onDecided={() => router.refresh()}
      />
      {deleteOpen && (
        <DeleteCourseDialog
          course={course}
          open
          onOpenChange={setDeleteOpen}
          onDeleted={() => router.push("/resultats")}
        />
      )}
      {searchOpen && (
        <TargetSearch courseId={course.id} onOpenChange={setSearchOpen} onSelect={pickTarget} />
      )}
      {other && (
        <MergeCoursesDialog
          courseA={current}
          courseB={other}
          open
          onOpenChange={(open) => !open && setOther(null)}
          onMerged={(keptId) =>
            keptId === course.id ? router.refresh() : router.push(`/courses/${keptId}`)
          }
        />
      )}
    </div>
  );
}

/**
 * Trouver l'épreuve à fusionner, **sans contrainte de date** : `/admin/doublons`
 * ne rapproche que des épreuves du même jour, et une jumelle mal datée lui
 * échappe. Un nombre seul cherche par identifiant, sinon par nom.
 */
function TargetSearch({
  courseId,
  onOpenChange,
  onSelect,
}: {
  courseId: number;
  onOpenChange: (open: boolean) => void;
  onSelect: (course: CourseBrief) => void;
}) {
  const [input, setInput] = useState("");
  const term = useDebounce(input.trim(), 300);
  const filter = /^\d+$/.test(term) ? { id: term } : { name: term };
  const results = useAdminCourses(1, filter, term.length > 0);
  const candidates = term ? results.data?.filter((c) => c.id !== courseId) : undefined;

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Fusionner avec une autre épreuve</DialogTitle>
          <DialogDescription>
            Cherchez l&apos;autre épreuve par son nom ou son numéro. Vous choisirez ensuite
            laquelle conserver, après un aperçu de ce que la fusion détruit.
          </DialogDescription>
        </DialogHeader>

        <Input
          type="search"
          aria-label="Chercher une épreuve"
          placeholder="Nom ou numéro de l'épreuve…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />

        {results.isFetching && <Skeleton className="h-20 w-full" />}

        <p role="status" aria-live="polite" className="text-[var(--tcn-text-faint)] text-sm">
          {candidates === undefined
            ? ""
            : candidates.length === 0
              ? "Aucune autre épreuve ne correspond à cette recherche."
              : `${candidates.length} ${plural(candidates.length, "épreuve trouvée", "épreuves trouvées")}.`}
        </p>

        {candidates && candidates.length > 0 && (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {candidates.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onSelect(c)}
                  className="w-full rounded-md border border-transparent p-2 text-left text-sm hover:bg-accent"
                >
                  <span className="block font-medium">
                    n° {c.id} · {c.name}
                  </span>
                  <span className="text-[var(--tcn-text-faint)] block text-xs">
                    {c.event_date ? formatDate(c.event_date) : "Date inconnue"} ·{" "}
                    {providerLabel(c.provider)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
