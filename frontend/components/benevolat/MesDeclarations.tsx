"use client";
import { Badge, Card } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useHydratedSession, useMyVolunteerDeclarations } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import { seasonLabel } from "@/lib/utils/season";

const STATUTS: Record<string, { label: string; variant: "neutral" | "orange" | "ink" }> = {
  en_attente: { label: "En attente", variant: "orange" },
  validee: { label: "Validée", variant: "ink" },
  refusee: { label: "Refusée", variant: "neutral" },
};

/** Déclarations faites par mon compte et leur statut (#1672) ; rien sans session. */
export function MesDeclarations() {
  const connecte = !!useHydratedSession().data;
  const declarations = useMyVolunteerDeclarations(connecte);

  if (!connecte) return null;

  return (
    <Card>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>
        Mes déclarations
      </h2>
      {declarations.isPending ? (
        <Skeleton className="mt-4 h-16 w-full" />
      ) : declarations.isError ? (
        <EmptyState
          bare
          title="Déclarations indisponibles"
          description="Vos déclarations n'ont pas pu être chargées. Réessayez plus tard."
        />
      ) : declarations.data.length === 0 ? (
        <EmptyState
          bare
          title="Aucune déclaration pour l'instant"
          description="Vos déclarations apparaîtront ici avec leur statut de validation."
        />
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0" }}>
          {declarations.data.map((d) => {
            const statut = STATUTS[d.status] ?? { label: d.status, variant: "neutral" as const };
            return (
              <li key={d.id} style={{ marginTop: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <strong>{d.title ?? "Action sans titre"}</strong>
                  <Badge variant={statut.variant}>{statut.label}</Badge>
                </div>
                <div style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>
                  Pour {d.athlete_prenom} {d.athlete_nom}, déclarée le {formatDate(d.created_at)} ({seasonLabel(d.season).toLowerCase()})
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
