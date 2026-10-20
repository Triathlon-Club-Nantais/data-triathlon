"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { TeammatesDialog } from "@/components/athletes/TeammatesDialog";
import { ClaimKind } from "@/components/admin/ClaimKind";
import { nomComplet } from "@/components/layout/AthletePicker";
import { useDecideResultClaim, useResultClaims } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { ClaimedAthlete, ResultClaimReview } from "@/lib/types";

const REFUS = { sujet: "réclamations de résultat", action: "valider les rattachements de fiche" };

/**
 * Réclamations d'un seul résultat (#1637), section distincte des demandes de
 * fiche entière dans la file commune. Déplacer passe par la réattribution du
 * back-office : résultat figé contre l'import, fiche d'origine purgée si vidée.
 */
const noms = (athletes: ClaimedAthlete[]) => athletes.map(nomComplet).join(", ");

export function ResultClaimsTable() {
  const [aComposer, setAComposer] = useState<ResultClaimReview | null>(null);
  const { data, isPending, error } = useResultClaims();
  const decider = useDecideResultClaim();

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
      toast.success(
        decision === "reject" ? "Réclamation refusée." : reclamation.kind === "team" ? "Demande traitée." : "Résultat déplacé.",
      );
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
            return (
              <TableRow key={r.id}>
                <TableCell>
                  <ClaimKind kind={r.kind} />
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
                </TableCell>
                <TableCell>
                  {r.kind === "team" ? (
                    <ul className="space-y-1 text-sm">
                      <li>
                        {r.teammates.length > 0
                          ? `Équipe actuelle : ${noms(r.teammates)}`
                          : `Fiche d'équipe : ${nomComplet(r.current_athlete)}`}
                      </li>
                      <li>
                        {r.proposed_teammates
                          ? `Après validation : ${noms(r.proposed_teammates)}`
                          : "À composer : la composition a été posée à la main."}
                      </li>
                      {r.claimant_has_result_on_course && <li>Cet athlète a déjà un résultat sur cette épreuve.</li>}
                    </ul>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      <li>
                        Fiche actuelle : {nomComplet(r.current_athlete)}
                        {r.current_athlete_results === 1
                          ? " (vidée par le déplacement, elle sera supprimée)"
                          : ` (${r.current_athlete_results} résultats)`}
                      </li>
                      <li>Vers : {r.claimant_athlete ? nomComplet(r.claimant_athlete) : "fiche détachée entre temps"}</li>
                      <li>
                        {r.licensee
                          ? `Licencié ${r.licensee.season} : ${nomComplet(r.licensee)}`
                          : "Aucun licencié de la saison"}
                      </li>
                    </ul>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    {r.kind === "team" ? (
                      r.proposed_teammates ? (
                        <Button
                          size="sm"
                          onClick={() => decide(r, "approve")}
                          disabled={decider.isPending}
                          aria-label={`Ajouter à l'équipe (${qui})`}
                        >
                          Ajouter à l&apos;équipe
                        </Button>
                      ) : (
                        <>
                          <Button size="sm" variant="outline" onClick={() => setAComposer(r)} disabled={decider.isPending}>
                            Composer l&apos;équipe
                          </Button>
                          <Button size="sm" onClick={() => decide(r, "approve")} disabled={decider.isPending}>
                            Clore la demande
                          </Button>
                        </>
                      )
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => decide(r, "approve")}
                        disabled={decider.isPending || r.claimant_athlete === null}
                        aria-label={`Déplacer le résultat réclamé par ${qui}`}
                      >
                        Déplacer le résultat
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
      {aComposer && (
        <TeammatesDialog
          resultat={{
            id: aComposer.participation.id,
            epreuve: aComposer.participation.course_name,
            date: aComposer.participation.event_date,
          }}
          equipiers={[
            ...(aComposer.teammates.length > 0 ? aComposer.teammates : [aComposer.current_athlete]),
            ...(aComposer.claimant_athlete ? [aComposer.claimant_athlete] : []),
          ]}
          onClose={() => setAComposer(null)}
        />
      )}
    </Card>
  );
}
