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
import { usePendingProviders, useMarkProviderHandled } from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";

export function PendingProvidersTable() {
  const { data, isLoading } = usePendingProviders();
  const mark = useMarkProviderHandled();

  if (isLoading) return <p className="text-muted-foreground">Chargement…</p>;
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground">Aucun fournisseur signalé.</p>;
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
  );
}
