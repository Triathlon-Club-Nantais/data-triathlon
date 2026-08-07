"use client";
import { useState } from "react";
import { ListOrdered, Pencil, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { eventTypeLabel } from "@/lib/constants";
import { useAdminCourses, TAILLE_PAGE_ADMIN } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import type { CourseBrief } from "@/lib/types";
import { DeleteCourseDialog } from "./DeleteCourseDialog";
import { CourseParticipationsDialog } from "./CourseParticipationsDialog";
import { EditCourseDialog } from "./EditCourseDialog";

/**
 * Le catalogue d'épreuves, côté administration (#117).
 *
 * **Paginé, et ce n'est pas cosmétique** : la base en compte 211 pour une
 * tranche de 50. Sans ces deux boutons, quatre épreuves sur cinq seraient
 * inatteignables depuis le back-office — donc ni corrigeables ni supprimables,
 * ce qui viderait SC-001 (« sans aucun accès direct à la base ») de son sens.
 *
 * **Pas de branche 401/403 ici**, contrairement à `PendingProvidersTable` :
 * `GET /courses` est une lecture publique, sans garde. Ces deux états seraient
 * inatteignables, et les tester exigerait de fabriquer une erreur que le serveur
 * ne peut pas produire (Principe VI).
 */
export function CoursesAdminTable() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAdminCourses(page);
  const session = useSession();
  const [aSupprimer, setASupprimer] = useState<CourseBrief | null>(null);
  const [aDetailler, setADetailler] = useState<CourseBrief | null>(null);
  const [aCorriger, setACorriger] = useState<CourseBrief | null>(null);

  // Le serveur reste seul juge (FR-009) : ces tests n'autorisent rien, ils
  // évitent de proposer un bouton qui rendrait 403.
  const peutSupprimer = session.data?.permissions.includes("courses:delete") ?? false;
  const peutCorriger = session.data?.permissions.includes("courses:write") ?? false;

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) {
    return (
      <EmptyState
        title="Catalogue indisponible"
        description="Les épreuves n'ont pas pu être chargées. Réessayez plus tard."
      />
    );
  }
  if (!data || (data.length === 0 && page === 1)) {
    return (
      <EmptyState
        title="Aucune épreuve"
        description="Le catalogue est vide : importez une épreuve depuis son URL de chronométrage."
      />
    );
  }

  // Une tranche incomplète est la dernière. `GET /courses` ne rend pas de total,
  // et en réclamer un pour deux boutons ne vaut pas un changement de contrat.
  const derniereTranche = data.length < TAILLE_PAGE_ADMIN;

  return (
    <>
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Épreuve</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Type</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((course) => (
              <TableRow key={course.id}>
                <TableCell className="max-w-xs truncate">{course.name}</TableCell>
                <TableCell>{formatDate(course.event_date)}</TableCell>
                {/* Le slug reste affiché tel quel s'il est inconnu de la table :
                    une administration qui masque « triathlon-xxl » derrière un
                    tiret cache justement l'épreuve à corriger. */}
                <TableCell>{eventTypeLabel(course.event_type)}</TableCell>
                <TableCell className="text-right">
                  {/* Trois pastilles **bordées et colorées au repos** : sans
                      contour un bouton-icône ne se lit pas comme un contrôle,
                      et sans couleur rien ne dit lequel détruit. Le survol
                      ajoute l'aplat. Le libellé porte le nom de l'épreuve,
                      sans quoi la page aligne cinquante « Supprimer »
                      indiscernables à la lecture d'écran ; `title` suffit à
                      l'infobulle, plutôt qu'installer @radix-ui/react-tooltip
                      pour trois boutons. */}
                  <div className="flex justify-end gap-1.5">
                    <Button
                      size="icon-sm"
                      variant="outline"
                      className="text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Voir les résultats"
                      aria-label={`Résultats — ${course.name}`}
                      onClick={() => setADetailler(course)}
                    >
                      <ListOrdered />
                    </Button>
                    {peutCorriger && (
                      <Button
                        size="icon-sm"
                        variant="outline"
                        className="border-primary/25 text-primary hover:border-primary/50 hover:bg-primary/10 hover:text-primary"
                        title="Corriger l'épreuve"
                        aria-label={`Corriger — ${course.name}`}
                        onClick={() => setACorriger(course)}
                      >
                        <Pencil />
                      </Button>
                    )}
                    {peutSupprimer && (
                      <Button
                        size="icon-sm"
                        variant="outline"
                        className="border-destructive/25 text-destructive hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
                        title="Supprimer l'épreuve"
                        aria-label={`Supprimer — ${course.name}`}
                        onClick={() => setASupprimer(course)}
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 1}
          onClick={() => setPage((courante) => Math.max(1, courante - 1))}
        >
          Page précédente
        </Button>
        <span className="text-muted-foreground text-sm">Page {page}</span>
        <Button
          variant="outline"
          size="sm"
          disabled={derniereTranche}
          onClick={() => setPage((courante) => courante + 1)}
        >
          Page suivante
        </Button>
      </div>

      {aSupprimer && (
        <DeleteCourseDialog
          course={aSupprimer}
          open
          onOpenChange={(ouvert) => !ouvert && setASupprimer(null)}
        />
      )}

      {aCorriger && (
        <EditCourseDialog
          course={aCorriger}
          open
          onOpenChange={(ouvert) => !ouvert && setACorriger(null)}
        />
      )}

      {aDetailler && (
        <CourseParticipationsDialog
          course={aDetailler}
          open
          onOpenChange={(ouvert) => !ouvert && setADetailler(null)}
        />
      )}
    </>
  );
}
