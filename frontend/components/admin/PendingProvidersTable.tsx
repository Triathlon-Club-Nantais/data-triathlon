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
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { usePendingProviders, useMarkProviderHandled } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";

/**
 * Ce que dit un refus ici (#115) : le composant ne lisait que `isLoading` et
 * `data`, et affichait « Aucun fournisseur signalé » sur un 403 — **un écran qui
 * ment**. Le signalement est public, la liste ne l'est pas ; sans distinction,
 * un modérateur mal composé conclut qu'il n'y a rien à traiter.
 */
const REFUS = { sujet: "signalements", action: "consulter les chronométreurs signalés" };

export function PendingProvidersTable() {
  const { data, isLoading, error } = usePendingProviders();
  const mark = useMarkProviderHandled();
  const session = useSession();
  // `pending_providers:read` a ouvert cette liste ; le `DELETE` qui retire un
  // signalement exige `pending_providers:handle`, attribuable séparément. Un
  // bouton offert sans ce pouvoir ne rend que des 403. Patron de
  // `CoursesAdminTable`.
  const peutTraiter =
    session.data?.permissions.includes("pending_providers:handle") ?? false;

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="Aucun fournisseur signalé"
        description="Tout fournisseur de chronométrage non reconnu lors d'un import apparaîtra ici."
      />
    );
  }

  async function handle(id: number) {
    try {
      await mark.mutateAsync(id);
      toast.success("Marqué comme traité.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {/* Sans elle, l'écran privé de son unique geste ne se distingue pas d'un
          écran cassé. Même formulation que `RolePermissionsEditor`, même libellé
          de pouvoir que l'inventaire de `core/permissions.py`. */}
      {!peutTraiter && (
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Cet écran est en consultation : marquer un signalement comme traité demande le
          pouvoir « Instruire les signalements ».
        </p>
      )}
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>URL</TableHead>
              <TableHead>Indice</TableHead>
              <TableHead>Signalé le</TableHead>
              {peutTraiter && <TableHead></TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="max-w-xs truncate">
                  <a href={p.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    {p.url}
                  </a>
                </TableCell>
                <TableCell>{p.provider_hint}</TableCell>
                <TableCell>{formatDate(p.reported_at)}</TableCell>
                {peutTraiter && (
                  <TableCell>
                    <Button size="sm" variant="outline" onClick={() => handle(p.id)} disabled={mark.isPending}>
                      Marquer comme traité
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
