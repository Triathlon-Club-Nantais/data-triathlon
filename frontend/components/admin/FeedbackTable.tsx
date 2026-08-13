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
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useFeedbackList } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { Feedback } from "@/lib/types";

const REFUS = { sujet: "retours utilisateurs", action: "consulter les retours utilisateurs" };

type ColonneTriable = "created_at" | "type" | "status";

const LIBELLE_STATUT: Record<Feedback["status"], string> = {
  nouveau: "Nouveau",
  en_cours: "En cours",
  traite: "Traité",
  ignore: "Ignoré",
};

/**
 * Trois colonnes triables (contracts/feedback-api.md), « Titre » ne l'est pas
 * — le contrat ne l'accepte pas en `sort`, et un clic qui rendrait 422 serait
 * pire qu'un en-tête inerte.
 */
function EnTeteTriable({
  colonne,
  label,
  actif,
  order,
  onTrier,
}: {
  colonne: ColonneTriable;
  label: string;
  actif: boolean;
  order: "asc" | "desc";
  onTrier: (colonne: ColonneTriable) => void;
}) {
  return (
    <TableHead>
      <button type="button" onClick={() => onTrier(colonne)} className="hover:underline">
        {label}
        {actif ? (order === "desc" ? " ↓" : " ↑") : ""}
      </button>
    </TableHead>
  );
}

export function FeedbackTable() {
  const [sort, setSort] = useState<ColonneTriable>("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const { data, isLoading, error } = useFeedbackList(sort, order);

  function trier(colonne: ColonneTriable) {
    if (colonne === sort) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSort(colonne);
      setOrder("desc");
    }
  }

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="Aucun retour utilisateur"
        description="Les signalements soumis depuis le site public apparaîtront ici."
      />
    );
  }

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <EnTeteTriable
              colonne="created_at"
              label="Date"
              actif={sort === "created_at"}
              order={order}
              onTrier={trier}
            />
            <EnTeteTriable
              colonne="type"
              label="Type"
              actif={sort === "type"}
              order={order}
              onTrier={trier}
            />
            <TableHead>Titre</TableHead>
            <EnTeteTriable
              colonne="status"
              label="Statut"
              actif={sort === "status"}
              order={order}
              onTrier={trier}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((f) => (
            <TableRow key={f.id}>
              <TableCell>{formatDate(f.created_at)}</TableCell>
              <TableCell>
                <Badge variant={f.type === "bug" ? "destructive" : "secondary"}>
                  {f.type === "bug" ? "Bug" : "Retour"}
                </Badge>
              </TableCell>
              <TableCell className="max-w-xs truncate">{f.title}</TableCell>
              <TableCell>{LIBELLE_STATUT[f.status]}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
