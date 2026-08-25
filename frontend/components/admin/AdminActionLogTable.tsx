"use client";
import { useState } from "react";
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
import { useAdminActionLog, TAILLE_PAGE_JOURNAL } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDateTime } from "@/lib/utils/date";
import { actionLabel, formatPayload } from "@/lib/admin-action-log";

const REFUS = { sujet: "gestes d'administration", action: "consulter le journal" };

/**
 * Le journal d'administration, en lecture (#501). Pagination locale, sans
 * refléter la page dans l'URL — patron de `QualityQueueTable`, plus simple
 * que la pagination `<Link>` du catalogue d'épreuves : rien ici n'a besoin
 * d'être partageable par URL.
 */
export function AdminActionLogTable() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAdminActionLog(page);

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }
  if (error) {
    return <EmptyState {...messageDeRefus(error, REFUS)} />;
  }
  if (!data || data.entries.length === 0) {
    return (
      <EmptyState
        title="Aucune entrée dans le journal"
        description="Les gestes d'administration effectués sur les données apparaîtront ici."
      />
    );
  }

  const pages = Math.max(1, Math.ceil(data.total / TAILLE_PAGE_JOURNAL));

  return (
    <div className="space-y-4">
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Auteur</TableHead>
              <TableHead>Geste</TableHead>
              <TableHead>Détail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.entries.map((entree) => (
              <TableRow key={entree.id}>
                <TableCell className="whitespace-nowrap">
                  {formatDateTime(entree.created_at)}
                </TableCell>
                <TableCell>{entree.user_name}</TableCell>
                <TableCell>{actionLabel(entree.action)}</TableCell>
                <TableCell className="text-sm text-[var(--tcn-text-faint)]">
                  {formatPayload(entree.payload).map(({ label, value }, i) => (
                    <div key={i}>
                      {label} : {value}
                    </div>
                  ))}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {pages > 1 && (
        <nav
          aria-label="Pagination du journal d'administration"
          className="flex items-center justify-between gap-3 rounded-xl border p-3 text-sm"
        >
          <span aria-current="page">
            Page {page} sur {pages} — {data.total} entrée{data.total > 1 ? "s" : ""}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ‹ Précédent
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Suivant ›
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
}
