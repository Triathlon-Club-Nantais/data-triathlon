"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import { useSession } from "@/lib/queries/auth";
import { useAdminAthlete } from "@/lib/queries/admin";
import { useDebounce } from "@/hooks/useDebounce";
import type { CourseBrief, Participation } from "@/lib/types";
import { ReassignParticipationDialog } from "./ReassignParticipationDialog";
import { EditAthleteDialog } from "./EditAthleteDialog";

/**
 * Les résultats d'une épreuve, d'où l'on atteint les gestes qui portent sur eux.
 *
 * C'est le chemin décrit par FR-016 : on descend d'une épreuve vers ses
 * résultats, puis vers leurs coureurs. Il n'existe pas d'annuaire de coureurs
 * administrable, et c'est un choix (spec §Hors périmètre).
 */
export function CourseParticipationsDialog({
  course,
  open,
  onOpenChange,
}: {
  course: CourseBrief;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [aRattacher, setARattacher] = useState<Participation | null>(null);
  const [coureurACorriger, setCoureurACorriger] = useState<number | null>(null);
  const [saisie, setSaisie] = useState("");
  const recherche = useDebounce(saisie, 300);
  const session = useSession();
  const peutRattacher =
    session.data?.permissions.includes("participations:reassign") ?? false;
  const peutCorrigerCoureur =
    session.data?.permissions.includes("athletes:write") ?? false;

  // La fiche complète, et non l'`AthleteBrief` du résultat : celui-ci n'a pas
  // de date de naissance, et l'enregistrer l'effacerait.
  const fiche = useAdminAthlete(coureurACorriger);

  // Sans le champ de recherche, sur une épreuve de 1811 participants, le
  // résultat mal rattaché qu'on vient déplacer est presque toujours hors des
  // cinquante premiers. La route accepte `q` : autant s'en servir.
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.adminCourseDetail(course.id, recherche),
    queryFn: () => apiClient.getCourse(course.id, { page_size: 50, q: recherche || undefined }),
    enabled: open,
  });

  // L'édition est ouverte quand sa fiche est **là**, pas quand elle est
  // demandée : fermer celle-ci sur un simple clic laisserait l'écran sans
  // aucune modale le temps du chargement, et pour toujours si la fiche échoue
  // (un rôle portant `athletes:write` sans `athletes:read` est une composition
  // légale). L'état se **déduit**, il ne se corrige pas dans un effet — un
  // `setState` en effet déclenche des rendus en cascade.
  const editionOuverte = coureurACorriger !== null && fiche.data !== undefined;

  return (
    <>
      <Dialog
        open={open && aRattacher === null && !editionOuverte}
        onOpenChange={onOpenChange}
      >
        <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Résultats — {course.name}</DialogTitle>
            <DialogDescription>
              Rattacher un résultat au bon coureur quand un scraper a créé un doublon
              d&apos;identité.
            </DialogDescription>
          </DialogHeader>

          <Input
            type="search"
            placeholder="Filtrer par nom ou prénom…"
            value={saisie}
            onChange={(evenement) => setSaisie(evenement.target.value)}
          />

          {fiche.isError && (
            <p className="text-destructive text-sm">
              La fiche de ce coureur n&apos;a pas pu être chargée — il faut le pouvoir
              « Consulter les fiches coureur » pour la corriger.
            </p>
          )}

          {isLoading && <Skeleton className="h-40 w-full" />}

          {data && data.participations.length === 0 && (
            <EmptyState
              title="Aucun résultat"
              description={
                recherche
                  ? "Aucun résultat ne correspond à cette recherche."
                  : "Cette épreuve ne porte aucun résultat."
              }
            />
          )}

          {data && data.participations.length > 0 && (
            <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto">
              {data.participations.map((participation) => (
                <li
                  key={participation.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b py-2 text-sm"
                >
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">
                      {participation.athlete.nom} {participation.athlete.prenom}
                    </span>
                    <span className="text-[var(--tcn-text-faint)] block text-xs">
                      Dossard {participation.bib_number ?? "—"} ·{" "}
                      {participation.total_time ?? participation.status}
                    </span>
                  </span>
                  {peutCorrigerCoureur && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setCoureurACorriger(participation.athlete.id)}
                    >
                      Corriger le coureur
                    </Button>
                  )}
                  {peutRattacher && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setARattacher(participation)}
                    >
                      Rattacher
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>

      {editionOuverte && fiche.data && (
        <EditAthleteDialog
          athlete={fiche.data}
          open
          onOpenChange={(ouvert) => !ouvert && setCoureurACorriger(null)}
        />
      )}

      {aRattacher && (
        <ReassignParticipationDialog
          participation={aRattacher}
          open
          onOpenChange={(ouvert) => !ouvert && setARattacher(null)}
        />
      )}
    </>
  );
}
