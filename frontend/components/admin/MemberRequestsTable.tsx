"use client";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useDecideMemberRequest, useMemberRequests } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { MemberRequestReview } from "@/lib/types";

const REFUS = { sujet: "demandes d'adhésion", action: "valider les demandes d'adhésion" };

/** File des demandes d'adhésion (#1785) : un compte connecté, non adhérent, demande à l'être. */
export function MemberRequestsTable() {
  const { data, isPending, error } = useMemberRequests();
  const decider = useDecideMemberRequest();

  if (isPending) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">Aucune demande d&apos;adhésion en attente.</p>;
  }

  async function decide(demande: MemberRequestReview, decision: "approve" | "reject") {
    try {
      await decider.mutateAsync({ id: demande.id, decision });
      toast.success(decision === "approve" ? "Adhésion validée." : "Demande refusée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nom</TableHead>
            <TableHead>Date de naissance</TableHead>
            <TableHead>Téléphone</TableHead>
            <TableHead>Adresse du compte</TableHead>
            <TableHead>Demandée le</TableHead>
            <TableHead className="sr-only">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((demande) => {
            const nom = `${demande.first_name} ${demande.last_name}`;
            return (
              <TableRow key={demande.id}>
                <TableCell className="font-semibold">{nom}</TableCell>
                <TableCell>{demande.birth_date ? formatDate(demande.birth_date) : "Non renseignée"}</TableCell>
                <TableCell>{demande.phone ?? "Non renseigné"}</TableCell>
                <TableCell>{demande.user.email}</TableCell>
                <TableCell>{formatDate(demande.created_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => decide(demande, "approve")}
                      disabled={decider.isPending}
                      aria-label={`Valider la demande de ${nom}`}
                    >
                      Valider
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => decide(demande, "reject")}
                      disabled={decider.isPending}
                      aria-label={`Refuser la demande de ${nom}`}
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
