"use client";
import { Card } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { messageDeRefus } from "@/lib/api/refus";
import { useValidatedVolunteerActions } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

const REPLI = "—";

const REFUS = {
  sujet: "actions de bénévolat validées",
  action: "consulter les actions de bénévolat validées",
};

/**
 * Actions de bénévolat validées d'un athlète, sur sa fiche publique (#781).
 * Invisible sans `athletes:volunteer_validate` (#779) — rendu nul, comme
 * `SeasonValidationPanel`/`AthleteAdminPanel` (#439) : aucune trace pour un
 * visiteur non habilité, ni section ni message de pouvoir manquant.
 *
 * Deux colonnes de texte seulement (titre, description) ne débordent jamais
 * un écran étroit comme le font les six colonnes d'`EventsTable`, donc pas
 * de duplication grille/cartes (#461, research.md D5 de la feature) — et
 * pas non plus `.tcn-table` (qui exige `display: grid` +
 * `gridTemplateColumns` sur chaque `<tr>` pour aligner les colonnes,
 * `frontend/AGENTS.md` #481) : un `<table>` natif aligne déjà correctement
 * deux colonnes sans geste supplémentaire, et porte sa propre sémantique de
 * tableau sans le moindre rôle ARIA à redéclarer.
 */
export function VolunteerActionsList({ athleteId }: { athleteId: number }) {
  const session = useSession();
  const peutConsulter =
    session.data?.permissions.includes("athletes:volunteer_validate") ?? false;
  const actions = useValidatedVolunteerActions(athleteId, peutConsulter);

  if (!peutConsulter) return null;

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 26px 16px" }}>
        <h2
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 22,
            fontWeight: 400,
            color: "var(--tcn-ink)",
            margin: 0,
          }}
        >
          Actions de bénévolat validées
        </h2>
      </div>

      {actions.isPending ? (
        <div style={{ padding: "0 26px 24px" }}>
          <Skeleton data-testid="volunteer-actions-skeleton" className="h-16 w-full" />
        </div>
      ) : actions.isError ? (
        <div style={{ padding: "0 26px 24px" }}>
          <EmptyState bare {...messageDeRefus(actions.error, REFUS)} />
        </div>
      ) : !actions.data || actions.data.length === 0 ? (
        <div style={{ padding: "0 26px 24px" }}>
          <EmptyState
            bare
            title="Aucune action de bénévolat validée"
            description="Les actions déclarées par l'athlète ou depuis l'administration apparaîtront ici une fois acceptées."
          />
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: ".04em",
                  color: "var(--tcn-text-faint)",
                  borderBottom: "1px solid var(--tcn-border)",
                }}
              >
                <th scope="col" style={{ textAlign: "left", padding: "0 26px 12px" }}>
                  Titre
                </th>
                <th scope="col" style={{ textAlign: "left", padding: "0 26px 12px" }}>
                  Description
                </th>
              </tr>
            </thead>
            <tbody>
              {actions.data.map((action) => (
                <tr key={action.id} style={{ borderTop: "1px solid var(--tcn-border-faint)" }}>
                  <td
                    style={{ padding: "12px 26px", fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}
                  >
                    {action.title ?? REPLI}
                  </td>
                  <td style={{ padding: "12px 26px", fontSize: 14, color: "var(--tcn-text-body)" }}>
                    {action.description ?? REPLI}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
