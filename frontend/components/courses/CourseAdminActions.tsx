"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
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
import { useHydratedSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
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
  const pouvoirs = useHydratedSession().data?.permissions ?? [];
  const peutCorriger = pouvoirs.includes("courses:write");
  const peutSupprimer = pouvoirs.includes("courses:delete");
  const peutTrancher = pouvoirs.includes("quality:override");
  const peutFusionner = peutSupprimer && pouvoirs.includes("courses:sources");

  const [correction, setCorrection] = useState(false);
  const [suppression, setSuppression] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [recherche, setRecherche] = useState(false);
  const [autre, setAutre] = useState<MergeableCourse | null>(null);

  if (!peutCorriger && !peutSupprimer && !peutTrancher) return null;

  const courante: MergeableCourse = {
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

  async function choisirCible(cible: CourseBrief) {
    try {
      // La liste ne porte ni total ni effectif TCN, dont la fusion a besoin pour
      // proposer la cible et avertir d'une perte de résultats du club.
      const synthese = await apiClient.getCourseSummary(cible.id);
      setAutre({ ...cible, total: synthese.total, tcn_count: synthese.tcn_count });
      setRecherche(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
      {peutCorriger && (
        <Button size="sm" variant="secondary" onClick={() => setCorrection(true)}>
          Corriger l&apos;épreuve
        </Button>
      )}
      {peutTrancher && (
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
      {peutFusionner && (
        <Button size="sm" variant="destructive" onClick={() => setRecherche(true)}>
          Fusionner avec une autre épreuve
        </Button>
      )}
      {peutSupprimer && (
        <Button size="sm" variant="destructive" onClick={() => setSuppression(true)}>
          Supprimer
        </Button>
      )}

      {correction && (
        <EditCourseDialog
          course={course}
          open
          onOpenChange={setCorrection}
          onSaved={() => router.refresh()}
        />
      )}
      <ReliabilityVerdictDialog
        course={course}
        verdict={verdict}
        onOpenChange={(ouvert) => !ouvert && setVerdict(null)}
        onDecided={() => router.refresh()}
      />
      {suppression && (
        <DeleteCourseDialog
          course={course}
          open
          onOpenChange={setSuppression}
          onDeleted={() => router.push("/resultats")}
        />
      )}
      {recherche && (
        <RechercheCible courseId={course.id} onOpenChange={setRecherche} onSelect={choisirCible} />
      )}
      {autre && (
        <MergeCoursesDialog
          courseA={courante}
          courseB={autre}
          open
          onOpenChange={(ouvert) => !ouvert && setAutre(null)}
          onMerged={(conserveeId) =>
            conserveeId === course.id ? router.refresh() : router.push(`/courses/${conserveeId}`)
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
function RechercheCible({
  courseId,
  onOpenChange,
  onSelect,
}: {
  courseId: number;
  onOpenChange: (ouvert: boolean) => void;
  onSelect: (course: CourseBrief) => void;
}) {
  const [saisie, setSaisie] = useState("");
  const terme = useDebounce(saisie.trim(), 300);
  const filtre = /^\d+$/.test(terme) ? { id: terme } : { name: terme };
  const resultats = useQuery({
    queryKey: ["course-merge-search", filtre],
    queryFn: () => apiClient.listCourses({ ...filtre, page_size: 20 }),
    enabled: terme.length > 0,
  });
  const candidates = resultats.data?.filter((c) => c.id !== courseId);

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
          value={saisie}
          onChange={(e) => setSaisie(e.target.value)}
        />

        {resultats.isFetching && <Skeleton className="h-20 w-full" />}

        {candidates && candidates.length === 0 && (
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Aucune autre épreuve ne correspond à cette recherche.
          </p>
        )}

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
