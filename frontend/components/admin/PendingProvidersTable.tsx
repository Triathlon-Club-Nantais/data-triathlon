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
    <Card className="p-0">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>URL</TableHead>
          <TableHead>Indice</TableHead>
          <TableHead>Signalé le</TableHead>
          <TableHead></TableHead>
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
            <TableCell>
              <Button size="sm" variant="outline" onClick={() => handle(p.id)} disabled={mark.isPending}>
                Traité
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    </Card>
  );
}
