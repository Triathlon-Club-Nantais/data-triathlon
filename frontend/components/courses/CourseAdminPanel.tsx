"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input, Modal } from "@/components/tcn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { DeleteCourseDialog } from "@/components/admin/DeleteCourseDialog";
import { EditCourseDialog } from "@/components/admin/EditCourseDialog";
import { MergeCoursesDialog, type MergeableCourse } from "@/components/admin/MergeCoursesDialog";
import { ReliabilityVerdictDialog, type Verdict } from "@/components/admin/ReliabilityVerdictDialog";
import { useDebounce } from "@/hooks/useDebounce";
import { apiClient } from "@/lib/api/client";
import { providerLabel } from "@/lib/labels";
import { useAdminCourses } from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";
import { plural } from "@/lib/utils/format";
import type { CourseBrief } from "@/lib/types";

/**
 * Les gestes d'administration d'une épreuve, depuis sa fiche publique (#1244).
 * Chargé à la demande par `CourseAdminActions`, une fois un pouvoir établi.
 *
 * Chaque entrée du menu « Gérer l'épreuve » teste **son** pouvoir, celui de la
 * route qu'elle appelle : la fusion en exige deux (`courses:sources` et
 * `courses:delete`, deux `Depends` côté backend). Les fenêtres sont celles du
 * back-office, réutilisées telles quelles ; seul leur dénouement change, la
 * page étant rendue côté serveur : `refresh()` après une correction,
 * redirection quand la fiche n'existe plus.
 */
export function CourseAdminPanel({
  course,
  total,
  tcnCount,
  permissions,
}: {
  course: CourseBrief;
  total: number;
  tcnCount: number;
  permissions: string[];
}) {
  const router = useRouter();
  const canEdit = permissions.includes("courses:write");
  const canDelete = permissions.includes("courses:delete");
  const canReview = permissions.includes("quality:override");
  const canMerge = canDelete && permissions.includes("courses:sources");

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [other, setOther] = useState<MergeableCourse | null>(null);

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

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
      {(canEdit || canReview || canDelete) && (
        <DropdownMenu>
          <DropdownMenuTrigger className="tcn-btn tcn-btn--sm tcn-btn--secondary">
            Gérer l&apos;épreuve
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-auto min-w-56">
            {canEdit && (
              <DropdownMenuItem className="tcn-cible-tactile" onClick={() => setEditOpen(true)}>Corriger l&apos;épreuve</DropdownMenuItem>
            )}
            {canReview && (
              <DropdownMenuSub>
                <DropdownMenuSubTrigger className="tcn-cible-tactile">Avis de fiabilité</DropdownMenuSubTrigger>
                <DropdownMenuSubContent>
                  <DropdownMenuItem className="tcn-cible-tactile" onClick={() => setVerdict("fiable")}>Marquer fiable</DropdownMenuItem>
                  <DropdownMenuItem className="tcn-cible-tactile" onClick={() => setVerdict("douteuse")}>Marquer douteuse</DropdownMenuItem>
                  <DropdownMenuItem className="tcn-cible-tactile" onClick={() => setVerdict("calcule")}>
                    Revenir à l&apos;avis calculé
                  </DropdownMenuItem>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
            )}
            {canDelete && (canEdit || canReview) && <DropdownMenuSeparator />}
            {canMerge && (
              <DropdownMenuItem className="tcn-cible-tactile" variant="destructive" onClick={() => setSearchOpen(true)}>
                Fusionner avec une autre épreuve
              </DropdownMenuItem>
            )}
            {canDelete && (
              <DropdownMenuItem className="tcn-cible-tactile" variant="destructive" onClick={() => setDeleteOpen(true)}>
                Supprimer l&apos;épreuve
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
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
        <TargetSearch
          courseId={course.id}
          onClose={() => setSearchOpen(false)}
          onPicked={(target) => {
            setOther(target);
            setSearchOpen(false);
          }}
        />
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
  onClose,
  onPicked,
}: {
  courseId: number;
  onClose: () => void;
  onPicked: (course: MergeableCourse) => void;
}) {
  const [input, setInput] = useState("");
  const [picking, setPicking] = useState<number | null>(null);
  const [pickError, setPickError] = useState<string | null>(null);
  const term = useDebounce(input.trim(), 300);
  const filter = /^\d+$/.test(term) ? { id: term } : { name: term };
  const results = useAdminCourses(1, filter, term.length > 0);
  const candidates =
    term && !results.isError ? results.data?.filter((c) => c.id !== courseId) : undefined;

  async function pick(target: CourseBrief) {
    setPicking(target.id);
    setPickError(null);
    try {
      // La liste ne porte ni total ni effectif TCN, dont la fusion a besoin pour
      // proposer la cible et avertir d'une perte de résultats du club.
      const summary = await apiClient.getCourseSummary(target.id);
      onPicked({ ...target, total: summary.total, tcn_count: summary.tcn_count });
    } catch (error) {
      setPickError((error as Error).message);
    } finally {
      setPicking(null);
    }
  }

  return (
    <Modal title="Fusionner avec une autre épreuve" onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-[var(--tcn-text-muted)]">
          Cherchez l&apos;autre épreuve par son nom ou son numéro. Vous choisirez ensuite
          laquelle conserver, après un aperçu de ce que la fusion détruit.
        </p>

        <Input
          type="search"
          aria-label="Chercher une épreuve"
          placeholder="Nom ou numéro de l'épreuve…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />

        {results.isFetching && <Skeleton className="h-20 w-full" />}

        <p role="status" aria-live="polite" className="text-[var(--tcn-text-faint)] text-sm">
          {term && results.isError
            ? "La recherche n'a pas abouti. Réessayez."
            : candidates === undefined
              ? ""
              : candidates.length === 0
                ? "Aucune autre épreuve ne correspond à cette recherche."
                : `${candidates.length} ${plural(candidates.length, "épreuve trouvée", "épreuves trouvées")}.`}
        </p>

        {pickError && (
          <p role="alert" className="text-sm text-[var(--tcn-danger-text)]">
            {pickError}
          </p>
        )}

        {candidates && candidates.length > 0 && (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {candidates.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => pick(c)}
                  disabled={picking !== null}
                  aria-busy={picking === c.id}
                  className="w-full cursor-pointer rounded-md border border-transparent p-2 text-left text-sm hover:bg-[var(--tcn-orange-08)] disabled:cursor-wait disabled:opacity-60"
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
      </div>
    </Modal>
  );
}
