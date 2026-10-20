"use client";
import { AnnonceStatut, Badge, Button, Card } from "@/components/tcn";
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
const STATUT_INCONNU = { label: "Statut inconnu", variant: "neutral" as const };

/** Déclarations faites par mon compte et leur statut (#1672) ; rien sans session. */
export function MesDeclarations() {
  const session = useHydratedSession().data;
  const declarations = useMyVolunteerDeclarations(!!session);

  if (!session) return null;

  const n = declarations.data?.length ?? 0;
  const charge = declarations.isPending || declarations.isFetching;
  const annonce = charge
    ? "Chargement de vos déclarations…"
    : declarations.isSuccess
      ? `${n} déclaration${n > 1 ? "s" : ""}.`
      : "";

  return (
    <Card>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>
        Mes déclarations
      </h2>
      <AnnonceStatut texte={annonce} busy={charge} />
      {declarations.isPending ? (
        <Skeleton data-testid="mes-declarations-squelette" className="mt-4 h-16 w-full" />
      ) : declarations.isError ? (
        <EmptyState
          bare
          className="py-4"
          title="Déclarations indisponibles"
          description="Vos déclarations n'ont pas pu être chargées."
          action={
            <Button variant="ghost" onClick={() => declarations.refetch()}>
              Réessayer
            </Button>
          }
        />
      ) : n === 0 ? (
        <p style={{ margin: "12px 0 0", color: "var(--tcn-text-faint)" }}>
          Vous n&apos;avez encore rien déclaré. Remplissez le formulaire ci-dessus pour créditer une action de bénévolat.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0" }}>
          {declarations.data.map((d, i) => {
            const statut = STATUTS[d.status] ?? STATUT_INCONNU;
            const pour = d.athlete_id === session.athlete?.id ? "Pour vous" : `Pour ${d.athlete_prenom} ${d.athlete_nom}`;
            return (
              <li
                key={d.id}
                style={i > 0 ? { borderTop: "1px solid var(--tcn-border-faint)", marginTop: 12, paddingTop: 12 } : undefined}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <strong className="min-w-0 break-words">{d.title ?? "Action sans titre"}</strong>
                  <Badge variant={statut.variant}>{statut.label}</Badge>
                </div>
                <div style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>
                  {pour}, déclarée le {formatDate(d.created_at)} ({seasonLabel(d.season).toLowerCase()})
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
