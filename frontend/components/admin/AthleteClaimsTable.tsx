"use client";
import Link from "next/link";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { nomComplet } from "@/components/layout/AthletePicker";
import { useAthleteClaims, useDecideAthleteClaim } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import { motCompte, plural } from "@/lib/utils/format";
import type { AthleteClaimReview } from "@/lib/types";

const REFUS = { sujet: "demandes de rattachement", action: "valider les rattachements de fiche" };

/**
 * File des demandes de rattachement (#1325). Aucune n'est validée d'office :
 * la liste d'adhérents ne porte que des adresses, elle n'est ici qu'un indice
 * à côté du licencié de la saison et des comptes déjà rattachés.
 */
export function AthleteClaimsTable() {
  const { data, isPending, error } = useAthleteClaims();
  const decider = useDecideAthleteClaim();

  if (isPending) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (data.length === 0) {
    return (
      <EmptyState
        title="Aucune demande de rattachement"
        description="Un utilisateur connecté qui choisit « C'est moi » sur une fiche athlète apparaîtra ici."
      />
    );
  }

  async function decide(demande: AthleteClaimReview, decision: "approve" | "reject") {
    try {
      await decider.mutateAsync({ id: demande.id, decision });
      toast.success(decision === "approve" ? "Fiche rattachée." : "Demande refusée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Compte</TableHead>
            <TableHead>Fiche demandée</TableHead>
            <TableHead>Indices</TableHead>
            <TableHead>Demandée le</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((demande) => {
            const qui = demande.user.display_name || demande.user.email;
            return (
              <TableRow key={demande.id}>
                <TableCell>
                  {demande.user.display_name && <div className="font-semibold">{demande.user.display_name}</div>}
                  <div className="text-sm text-muted-foreground">{demande.user.email}</div>
                </TableCell>
                <TableCell>
                  <Link href={`/athletes/${demande.athlete.id}`} className="underline underline-offset-2">
                    {nomComplet(demande.athlete)}
                  </Link>
                  {demande.athlete.club && (
                    <div className="text-sm text-muted-foreground">{demande.athlete.club}</div>
                  )}
                </TableCell>
                <TableCell>
                  <ul className="space-y-1 text-sm">
                    <li>
                      {demande.licensee
                        ? `Licencié ${demande.licensee.season} : ${nomComplet(demande.licensee)}`
                        : "Aucun licencié de la saison"}
                    </li>
                    <li>
                      {demande.email_on_member_list
                        ? "Adresse sur la liste d'adhérents"
                        : "Adresse absente de la liste d'adhérents"}
                    </li>
                    {demande.linked_accounts > 0 && (
                      <li>
                        {motCompte(demande.linked_accounts, "compte")} déjà{" "}
                        {plural(demande.linked_accounts, "rattaché")}
                      </li>
                    )}
                  </ul>
                </TableCell>
                <TableCell>{formatDate(demande.created_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => decide(demande, "approve")}
                      disabled={decider.isPending}
                      aria-label={`Valider la demande de ${qui}`}
                    >
                      Valider
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => decide(demande, "reject")}
                      disabled={decider.isPending}
                      aria-label={`Refuser la demande de ${qui}`}
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
    </Card>
  );
}
