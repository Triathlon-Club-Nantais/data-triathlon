"use client";
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
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import {
  useAdminDeleteVolunteerDeclaration,
  useAllVolunteerDeclarations,
  useValidateVolunteerDeclaration,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { AdminVolunteerDeclaration } from "@/lib/types";

const REFUS = { sujet: "déclarations de bénévolat", action: "consulter les déclarations de bénévolat" };

/**
 * Vue d'ensemble admin des déclarations de bénévolat (#751, US3/US4/US5) —
 * tous les membres, tous les statuts (FR-010). Valider et supprimer exigent
 * `benevolat:manage` (le pouvoir qui a ouvert cette page est `benevolat:read`
 * seul — patron `PendingProvidersTable`, pas d'inclusion implicite entre les
 * deux, cf. `/speckit-analyze` finding U1).
 */
export function AdminVolunteerDeclarationTable() {
  const { data, isLoading, error } = useAllVolunteerDeclarations();
  const valider = useValidateVolunteerDeclaration();
  const supprimer = useAdminDeleteVolunteerDeclaration();
  const session = useSession();
  const confirmerLeDanger = useDangerConfirm();
  const peutGerer = session.data?.permissions.includes("benevolat:manage") ?? false;

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="Aucune déclaration de bénévolat"
        description="Les auto-déclarations et les déclarations créées pour un membre apparaîtront ici."
      />
    );
  }

  async function onValidate(id: number) {
    try {
      await valider.mutateAsync(id);
      toast.success("Déclaration validée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function onDelete(declaration: AdminVolunteerDeclaration) {
    const confirme = await confirmerLeDanger({
      titre: `Supprimer « ${declaration.title} » ?`,
      description: "Cette déclaration sera définitivement supprimée, sans trace.",
      libelleAction: "Supprimer",
    });
    if (!confirme) return;
    try {
      await supprimer.mutateAsync(declaration.id);
      toast.success("Déclaration supprimée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {!peutGerer && (
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Cet écran est en consultation : valider ou supprimer une déclaration demande le
          pouvoir « Instruire les déclarations de bénévolat ».
        </p>
      )}
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Membre</TableHead>
              <TableHead>Titre</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead>Créée le</TableHead>
              {peutGerer && <TableHead></TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.id}>
                <TableCell>{d.beneficiary_display_name || d.beneficiary_email}</TableCell>
                <TableCell className="max-w-xs truncate">{d.title}</TableCell>
                <TableCell>
                  <Badge variant={d.status === "validee" ? "default" : "secondary"}>
                    {d.status === "validee" ? "Validée" : "En attente"}
                  </Badge>
                </TableCell>
                <TableCell>{formatDate(d.created_at)}</TableCell>
                {peutGerer && (
                  <TableCell className="flex gap-2">
                    {d.status === "en_attente" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onValidate(d.id)}
                        disabled={valider.isPending}
                      >
                        Valider
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onDelete(d)}
                      disabled={supprimer.isPending}
                    >
                      Supprimer
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
