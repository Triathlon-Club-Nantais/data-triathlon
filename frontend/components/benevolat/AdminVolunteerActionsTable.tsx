"use client";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
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
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import {
  useAcceptVolunteerAction,
  useDeleteVolunteerAction,
  usePendingVolunteerActions,
  useRejectVolunteerAction,
} from "@/lib/queries/admin";
import { queryKeys } from "@/lib/queries/keys";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { AdminVolunteerActionOut } from "@/lib/types";

const REPLI = "—";

const REFUS = {
  sujet: "crédits d'athlète en attente",
  action: "traiter les déclarations de crédit d'athlète",
};

/**
 * Écran de validation admin des déclarations de crédit d'athlète (#779,
 * jamais construit avant #817) — file d'attente, accepter, refuser. Aucune
 * bascule consultation/gestion : le pouvoir qui ouvre cet écran
 * (`athletes:volunteer_validate`) est déjà celui qui agit, contrairement au
 * patron de l'ancien `AdminVolunteerDeclarationTable.tsx` (#751, retiré par
 * #816). Pas de confirmation destructive : accepter/refuser change un
 * statut, réversible par l'action inverse — la suppression, elle
 * destructive, est #818.
 */
export function AdminVolunteerActionsTable() {
  const qc = useQueryClient();
  const { data, isLoading, error } = usePendingVolunteerActions();
  const accepter = useAcceptVolunteerAction();
  const refuser = useRejectVolunteerAction();
  const supprimer = useDeleteVolunteerAction();
  const confirmerLeDanger = useDangerConfirm();

  if (isLoading) return <Skeleton data-testid="admin-volunteer-actions-skeleton" className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="Aucune déclaration en attente"
        description="Les déclarations soumises par un membre depuis la page publique de bénévolat apparaîtront ici."
      />
    );
  }

  async function onAccept(id: number) {
    try {
      await accepter.mutateAsync(id);
      toast.success("Déclaration acceptée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function onReject(id: number) {
    try {
      await refuser.mutateAsync(id);
      toast.success("Déclaration refusée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function onDelete(action: AdminVolunteerActionOut) {
    if (
      !(await confirmerLeDanger({
        titre: `Supprimer la déclaration de ${action.athlete_prenom} ${action.athlete_nom} ?`,
        description: "La déclaration disparaît définitivement.",
      }))
    ) {
      return;
    }
    try {
      await supprimer.mutateAsync(action.id, {
        onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pendingVolunteerActions() }),
      });
      toast.success("Déclaration supprimée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Athlète</TableHead>
            <TableHead>Titre</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Déclarée le</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((action) => (
            <TableRow key={action.id}>
              <TableCell>
                {action.athlete_prenom} {action.athlete_nom}
              </TableCell>
              <TableCell className="max-w-xs truncate">{action.title ?? REPLI}</TableCell>
              <TableCell className="max-w-md truncate">{action.description ?? REPLI}</TableCell>
              <TableCell>{formatDate(action.created_at)}</TableCell>
              <TableCell>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onAccept(action.id)}
                    disabled={accepter.isPending || refuser.isPending || supprimer.isPending}
                    aria-label={`Accepter — ${action.athlete_prenom} ${action.athlete_nom}`}
                  >
                    Accepter
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onReject(action.id)}
                    disabled={accepter.isPending || refuser.isPending || supprimer.isPending}
                    aria-label={`Refuser — ${action.athlete_prenom} ${action.athlete_nom}`}
                  >
                    Refuser
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => onDelete(action)}
                    disabled={accepter.isPending || refuser.isPending || supprimer.isPending}
                    aria-label={`Supprimer — ${action.athlete_prenom} ${action.athlete_nom}`}
                  >
                    Supprimer
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
