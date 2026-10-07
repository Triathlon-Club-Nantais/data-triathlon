"use client";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Button, Card } from "@/components/tcn";
import { useAthleteAliases, useRemoveAthleteAlias } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type { AthleteAlias } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

export const VARIANTS_ANCHOR = "variantes";

function spelling(alias: AthleteAlias) {
  return `${alias.last_name_key.toUpperCase()} ${alias.first_name_key}`;
}

/**
 * Les variantes de graphie d'une fiche (#1242) : une fusion rattache la graphie
 * absorbée à la fiche gardée, et l'import y range désormais les résultats publiés
 * sous elle. Sans `athletes:write` ou sans variante, rien n'est rendu.
 *
 * Le panneau n'existe qu'après la session et la lecture des variantes : l'ancre
 * `#variantes` (lien de la revue d'identité) ne peut pas y mener seule, d'où le
 * défilement à l'arrivée des données.
 *
 * `DangerConfirm` déclaratif : la fiche athlète est hors de tout
 * `DangerConfirmProvider` (patron de `VolunteerActionsList`).
 */
export function AthleteVariantsPanel({ athleteId }: { athleteId: number }) {
  const session = useHydratedSession();
  const allowed = session.data?.permissions.includes("athletes:write") ?? false;
  const variants = useAthleteAliases(athleteId, allowed);
  const removal = useRemoveAthleteAlias();
  const [toRemove, setToRemove] = useState<AthleteAlias | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const visible =
    allowed && (variants.isError || (variants.data?.aliases.length ?? 0) > 0);

  useEffect(() => {
    if (visible && window.location.hash === `#${VARIANTS_ANCHOR}`)
      card.current?.scrollIntoView();
  }, [visible]);

  if (!visible) return null;

  async function remove() {
    if (!toRemove) return;
    try {
      await removal.mutateAsync({ athleteId, aliasId: toRemove.id });
      toast.success("Variante retirée.");
      setToRemove(null);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  return (
    <div id={VARIANTS_ANCHOR} ref={card} style={{ scrollMarginTop: "80px" }}>
      <Card>
        <h2
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 22,
            fontWeight: 400,
            margin: "0 0 6px",
          }}
        >
          Variantes d&apos;identité
        </h2>
        <p
          style={{
            margin: "0 0 12px",
            fontSize: 14,
            color: "var(--tcn-text-muted)",
          }}
        >
          Graphies normalisées (sans accents, espaces ni ponctuation) rattachées à cette
          fiche par une fusion : l&apos;import y range les résultats publiés
          sous elles.
        </p>
        {variants.isError && (
          <p
            role="alert"
            style={{ margin: 0, fontSize: 14, color: "var(--tcn-danger-text)" }}
          >
            Les variantes de cette fiche n&apos;ont pas pu être lues.
          </p>
        )}
        {variants.data && (
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              display: "grid",
              gap: 8,
            }}
          >
            {variants.data.aliases.map((alias) => (
              <li
                key={alias.id}
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <span style={{ fontWeight: 700 }}>{spelling(alias)}</span>
                <span style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
                  depuis le {formatDate(alias.created_at)}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setToRemove(alias)}
                  aria-label={`Retirer la variante ${spelling(alias)}`}
                >
                  Retirer
                </Button>
              </li>
            ))}
          </ul>
        )}

        <DangerConfirm
          open={toRemove !== null}
          onOpenChange={(open) => {
            if (!open && !removal.isPending) setToRemove(null);
          }}
          titre={toRemove ? `Retirer la variante ${spelling(toRemove)} ?` : ""}
          description="L'import ne rattachera plus cette graphie à la fiche. Les résultats déjà rattachés restent en place."
          libelleAction="Retirer"
          enAttente={removal.isPending}
          onConfirm={remove}
        />
      </Card>
    </div>
  );
}
