"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ClaimKind } from "@/components/admin/ClaimKind";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
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
 * Relais (#1739) : sans équipiers, la fiche du membre s'ajoute à côté du
 * porteur en un clic, ou remplace une étiquette d'équipe (porteur sans prénom),
 * avec confirmation si celle-ci est supprimée. Avec des équipiers, l'admin la
 * complète par « Attribuer aux équipiers », qui exige `participations:reassign`
 * et valide la réclamation dans le même geste.
 *
 * `titreId` : titre de la section, qui reçoit le focus quand la ligne traitée
 * disparaît avec sa modale.
 */
export function ResultClaimsTable({ titreId }: { titreId?: string }) {
  const { data, isPending, error } = useResultClaims();
  const decider = useDecideResultClaim();
  const peutAttribuer = useHydratedSession().data?.permissions.includes("participations:reassign") ?? false;
  const [aCompleter, setACompleter] = useState<ResultClaimReview | null>(null);
  const [aConfirmer, setAConfirmer] = useState<ResultClaimReview | null>(null);
  const titre = useRef<HTMLElement | null>(null);

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
      const valide = dejaDansLEquipe(reclamation)
        ? "Réclamation validée."
        : reclamation.participation.is_relay
          ? "Fiche ajoutée à l'équipe."
          : "Résultat déplacé.";
      toast.success(decision === "approve" ? valide : "Réclamation refusée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  function completer(reclamation: ResultClaimReview) {
    // Lu avant l'invalidation : une file vidée démonte le tableau, pas le titre de la section.
    titre.current = titreId ? document.getElementById(titreId) : null;
    setACompleter(reclamation);
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
            const etiquette = p.is_relay && p.teammates.length === 0 && !r.current_athlete.prenom;
            const ficheSupprimee = r.current_athlete_results === 1 && (!p.is_relay || etiquette);
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
                  {p.is_relay && <div className="text-sm">Équipe : {p.team_name || "nom inconnu"}</div>}
                </TableCell>
                <TableCell>
                  <ul className="space-y-1 text-sm">
                    {p.teammates.length > 0 ? (
                      <li>
                        Équipiers actuels :
                        <ul aria-label="Équipiers actuels" className="list-disc pl-5">
                          {p.teammates.map((equipier) => (
                            <li key={equipier.id}>{nomComplet(equipier)}</li>
                          ))}
                        </ul>
                      </li>
                    ) : (
                      <li>
                        Fiche actuelle : {nomComplet(r.current_athlete)}
                        {p.is_relay && !etiquette
                          ? " (gardée dans l'équipe)"
                          : ficheSupprimee
                            ? p.is_relay
                              ? " (n'aura plus aucun résultat, elle sera supprimée)"
                              : " (vidée par le déplacement, elle sera supprimée)"
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
                    {dejaDansLEquipe(r) ? (
                      <Button
                        size="sm"
                        onClick={() => decide(r, "approve")}
                        disabled={decider.isPending}
                        aria-label={`Valider la réclamation de ${qui}`}
                      >
                        Valider
                      </Button>
                    ) : p.teammates.length > 0 ? (
                      peutAttribuer ? (
                        <Button
                          size="sm"
                          onClick={() => completer(r)}
                          disabled={decider.isPending || r.claimant_athlete === null}
                          aria-label={`Attribuer aux équipiers, avec ${qui}`}
                        >
                          Attribuer aux équipiers
                        </Button>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Demandez à un administrateur disposant de « Rattacher un résultat ».
                        </p>
                      )
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => (etiquette && ficheSupprimee ? setAConfirmer(r) : decide(r, "approve"))}
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
          onClose={(attribue) => {
            setACompleter(null);
            // Après le démontage de la modale, qui sinon rend le focus à un bouton disparu.
            if (attribue) setTimeout(() => titre.current?.focus());
          }}
          reclamation={{
            de: aCompleter.user.display_name || aCompleter.user.email,
            athleteId: aCompleter.claimant_athlete.id,
            valider: () => decider.mutateAsync({ id: aCompleter.id, decision: "approve" }),
          }}
        />
      )}
      <DangerConfirm
        open={aConfirmer !== null}
        onOpenChange={(ouvert) => !ouvert && setAConfirmer(null)}
        titre={`Ajouter à l'équipe la fiche de ${aConfirmer ? aConfirmer.user.display_name || aConfirmer.user.email : ""} ?`}
        description={`La fiche « ${aConfirmer ? nomComplet(aConfirmer.current_athlete) : ""} » sera supprimée, elle n'a plus d'autre résultat.`}
        libelleAction="Ajouter à l'équipe"
        enAttente={decider.isPending}
        onConfirm={async () => {
          if (aConfirmer) await decide(aConfirmer, "approve");
          setAConfirmer(null);
        }}
      />
    </Card>
  );
}

/** Le membre figure déjà dans l'équipe : il ne reste qu'à clore sa réclamation. */
function dejaDansLEquipe(r: ResultClaimReview): boolean {
  return r.participation.teammates.some((equipier) => equipier.id === r.claimant_athlete?.id);
}
