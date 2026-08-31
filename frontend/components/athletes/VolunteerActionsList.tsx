"use client";
import { Card } from "@/components/tcn";
import { useValidatedVolunteerActions } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

const REPLI = "—";

/**
 * Actions de bénévolat validées d'un athlète, sur sa fiche publique (#781).
 * Invisible sans `athletes:volunteer_validate` (#779) — rendu nul, comme
 * `SeasonValidationPanel`/`AthleteAdminPanel` (#439) : aucune trace pour un
 * visiteur non habilité, ni section ni message de pouvoir manquant.
 *
 * Patron `.tcn-table` simplifié — deux colonnes de texte seulement (titre,
 * description) ne débordent jamais un écran étroit comme le font les six
 * colonnes d'`EventsTable`, donc pas de duplication grille/cartes (#461,
 * research.md D5 de la feature).
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

      {!actions.data || actions.data.length === 0 ? (
        <div style={{ padding: "0 26px 24px", color: "var(--tcn-text-faint)", fontSize: 14 }}>
          {actions.isPending ? null : "Aucune action de bénévolat validée pour cet athlète."}
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="tcn-table" role="table" style={{ width: "100%" }}>
            <thead role="rowgroup">
              <tr
                role="row"
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: ".04em",
                  color: "var(--tcn-text-faint)",
                  borderBottom: "1px solid var(--tcn-border)",
                }}
              >
                <th role="columnheader" scope="col" style={{ textAlign: "left", padding: "0 26px 12px" }}>
                  Titre
                </th>
                <th role="columnheader" scope="col" style={{ textAlign: "left", padding: "0 26px 12px" }}>
                  Description
                </th>
              </tr>
            </thead>
            <tbody role="rowgroup">
              {actions.data.map((action) => (
                <tr
                  key={action.id}
                  role="row"
                  style={{ borderTop: "1px solid var(--tcn-border-faint)" }}
                >
                  <td
                    role="cell"
                    style={{ padding: "12px 26px", fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}
                  >
                    {action.title ?? REPLI}
                  </td>
                  <td role="cell" style={{ padding: "12px 26px", fontSize: 14, color: "var(--tcn-text-body)" }}>
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
