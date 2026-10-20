"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ClaimKind } from "@/components/admin/ClaimKind";
import { nomComplet } from "@/components/layout/AthletePicker";
import { TeammatesDialog } from "@/components/athletes/TeammatesDialog";
import { useDecideResultClaim, useResultClaims } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { ResultClaimReview } from "@/lib/types";

const REFUS = { sujet: "réclamations de résultat", action: "valider les rattachements de fiche" };

/**
 * Réclamations d'un seul résultat (#1637), section distincte des demandes de
 * fiche entière dans la file commune. Déplacer passe par la réattribution du
 * back-office : résultat figé contre l'import, fiche d'origine purgée si vidée.
 *
 * Relais (#1739) : sans équipiers, la fiche du membre devient l'équipe en un
 * clic ; avec, l'admin la complète par « Attribuer aux équipiers », qui exige
 * `participations:reassign`, puis la réclamation se clôt.
 */
export function ResultClaimsTable() {
  const { data, isPending, error } = useResultClaims();
  const decider = useDecideResultClaim();
  const peutAttribuer = useHydratedSession().data?.permissions.includes("participations:reassign") ?? false;
  const [aCompleter, setACompleter] = useState<ResultClaimReview | null>(null);

  if (isPending) return <Skeleton className="h-32 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (data.length === 0) {
    return (
      <EmptyState
        title="Aucun résultat réclamé"
        description="Un adhérent rattaché qui choisit « Ce résultat est à moi » sur un résultat apparaîtra ici."
      />
    );
  }

  async function decide(reclamation: ResultClaimReview, decision: "approve" | "reject") {
    try {
      await decider.mutateAsync({ id: reclamation.id, decision });
      const valide = reclamation.participation.is_relay ? "Fiche ajoutée à l'équipe." : "Résultat déplacé.";
      toast.success(decision === "approve" ? valide : "Réclamation refusée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Sorte</TableHead>
            <TableHead>Compte</TableHead>
            <TableHead>Résultat réclamé</TableHead>
            <TableHead>Déplacement</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((r) => {
            const qui = r.user.display_name || r.user.email;
            const p = r.participation;
            const equipe = p.teammates.map(nomComplet).join(", ");
            return (
              <TableRow key={r.id}>
                <TableCell>
                  <ClaimKind kind="result" />
                </TableCell>
                <TableCell>
                  {r.user.display_name && <div className="font-semibold">{r.user.display_name}</div>}
                  <div className="text-sm text-muted-foreground">{r.user.email}</div>
                </TableCell>
                <TableCell>
                  <Link href={`/courses/${p.course_id}/participations/${p.id}`} className="underline underline-offset-2">
                    {p.course_name}
                  </Link>
                  <div className="text-sm text-muted-foreground">
                    {[formatDate(p.event_date), p.bib_number && `dossard ${p.bib_number}`, p.total_time, p.club, p.category]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                  {p.is_relay && <div className="text-sm">Équipe : {p.team_name || "sans nom"}</div>}
                </TableCell>
                <TableCell>
                  <ul className="space-y-1 text-sm">
                    {p.teammates.length > 0 ? (
                      <li>Équipiers actuels : {equipe}</li>
                    ) : (
                      <li>
                        Fiche actuelle : {nomComplet(r.current_athlete)}
                        {r.current_athlete_results === 1
                          ? " (vidée par le déplacement, elle sera supprimée)"
                          : ` (${r.current_athlete_results} résultats)`}
                      </li>
                    )}
                    <li>
                      {p.is_relay ? "À ajouter" : "Vers"} :{" "}
                      {r.claimant_athlete ? nomComplet(r.claimant_athlete) : "fiche détachée entre temps"}
                    </li>
                    <li>
                      {r.licensee
                        ? `Licencié ${r.licensee.season} : ${nomComplet(r.licensee)}`
                        : "Aucun licencié de la saison"}
                    </li>
                  </ul>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    {p.teammates.length > 0 ? (
                      peutAttribuer ? (
                        <Button
                          size="sm"
                          onClick={() => setACompleter(r)}
                          disabled={decider.isPending || r.claimant_athlete === null}
                          aria-label={`Attribuer aux équipiers, avec ${qui}`}
                        >
                          Attribuer aux équipiers
                        </Button>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Compléter l&apos;équipe demande le pouvoir de réattribuer les résultats.
                        </p>
                      )
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => decide(r, "approve")}
                        disabled={decider.isPending || r.claimant_athlete === null}
                        aria-label={
                          p.is_relay ? `Ajouter à l'équipe la fiche de ${qui}` : `Déplacer le résultat réclamé par ${qui}`
                        }
                      >
                        {p.is_relay ? "Ajouter à l'équipe" : "Déplacer le résultat"}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => decide(r, "reject")}
                      disabled={decider.isPending}
                      aria-label={`Refuser la réclamation de ${qui}`}
                    >
                      Refuser
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {aCompleter?.claimant_athlete && (
        <TeammatesDialog
          resultat={{
            id: aCompleter.participation.id,
            epreuve: aCompleter.participation.course_name,
            date: aCompleter.participation.event_date,
          }}
          equipiers={[...aCompleter.participation.teammates, aCompleter.claimant_athlete]}
          onClose={() => setACompleter(null)}
          onAttribue={() => decider.mutateAsync({ id: aCompleter.id, decision: "approve" })}
        />
      )}
    </Card>
  );
}
