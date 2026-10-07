"use client";
import { useState } from "react";
import { toast } from "sonner";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Button, Card } from "@/components/tcn";
import { useAthleteAliases, useRemoveAthleteAlias } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type { AthleteAlias } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

export const ANCRE_VARIANTES = "variantes";

function graphie(alias: AthleteAlias) {
  return `${alias.last_name_key.toUpperCase()} ${alias.first_name_key}`;
}

/**
 * Les variantes de graphie d'une fiche (#1242) : une fusion rattache la graphie
 * absorbée à la fiche gardée, et l'import y range désormais les résultats publiés
 * sous elle. Sans `athletes:write` ou sans variante, rien n'est rendu.
 *
 * `DangerConfirm` déclaratif : la fiche athlète est hors de tout
 * `DangerConfirmProvider` (patron de `VolunteerActionsList`).
 */
export function AthleteVariantsPanel({ athleteId }: { athleteId: number }) {
  const session = useHydratedSession();
  const autorise = session.data?.permissions.includes("athletes:write") ?? false;
  const variantes = useAthleteAliases(athleteId, autorise);
  const retrait = useRemoveAthleteAlias();
  const [aRetirer, setARetirer] = useState<AthleteAlias | null>(null);

  if (!autorise || !variantes.data?.aliases.length) return null;

  async function retirer() {
    if (!aRetirer) return;
    try {
      await retrait.mutateAsync({ athleteId, aliasId: aRetirer.id });
      toast.success("Variante retirée.");
      setARetirer(null);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <Card id={ANCRE_VARIANTES}>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, margin: "0 0 6px" }}>
        Variantes d&apos;identité
      </h2>
      <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--tcn-text-muted)" }}>
        Graphies rattachées à cette fiche par une fusion : l&apos;import y range les résultats publiés sous
        elles.
      </p>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
        {variantes.data.aliases.map((alias) => (
          <li key={alias.id} style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontWeight: 700 }}>{graphie(alias)}</span>
            <span style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>depuis le {formatDate(alias.created_at)}</span>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setARetirer(alias)}
              aria-label={`Retirer la variante ${graphie(alias)}`}
            >
              Retirer
            </Button>
          </li>
        ))}
      </ul>

      <DangerConfirm
        open={aRetirer !== null}
        onOpenChange={(ouvert) => {
          if (!ouvert && !retrait.isPending) setARetirer(null);
        }}
        titre={aRetirer ? `Retirer la variante ${graphie(aRetirer)} ?` : ""}
        description="L'import ne rattachera plus cette graphie à la fiche. Les résultats déjà rattachés restent en place."
        libelleAction="Retirer"
        enAttente={retrait.isPending}
        onConfirm={retirer}
      />
    </Card>
  );
}
