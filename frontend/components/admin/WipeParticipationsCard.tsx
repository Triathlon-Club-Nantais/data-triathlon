"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useParticipationsWipeImpact, useWipeAllParticipations } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { motCompte, plural } from "@/lib/utils/format";

const MOT_DE_CONFIRMATION = "SUPPRIMER";

/**
 * Repartir d'une base de résultats propre (#384) — par exemple avant un
 * rescrape complet suite à un changement de logique d'import.
 *
 * Vit sur `/admin/maintenance` (#499) : le geste n'a rien à faire sur
 * l'écran où l'on corrige une date. `Course` et `course_sources` restent
 * intacts — c'est ce qui rend un rescrape possible juste après, sans tout
 * réimporter depuis les URLs sources.
 *
 * **Le serveur reste seul juge** (FR-009 du domaine #115) : ce test de
 * pouvoir n'autorise rien, il évite de proposer un bouton qui rendrait 403.
 */
export function WipeParticipationsCard() {
  const [ouvert, setOuvert] = useState(false);
  const session = useSession();
  const impact = useParticipationsWipeImpact(ouvert);
  const purge = useWipeAllParticipations();

  const peutPurger = session.data?.permissions.includes("participations:wipe_all") ?? false;
  if (!peutPurger) return null;

  async function confirmer() {
    try {
      const resultat = await purge.mutateAsync();
      const p = resultat.participations_deleted;
      const a = resultat.athletes_purged;
      toast.success(
        `${motCompte(p, "résultat")} ${plural(p, "supprimé")}, ` +
          `${motCompte(a, "fiche")} athlète ${plural(a, "purgée")}.`,
      );
      setOuvert(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Purger les résultats</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Vide entièrement les résultats pour repartir d&apos;une base propre —
            avant un rescrape complet, par exemple. Les épreuves et leurs sources
            restent intactes ; seuls les résultats et les fiches athlète qu&apos;ils
            laissent vides sont détruits.
          </p>
          <Button variant="destructive" onClick={() => setOuvert(true)}>
            Purger tous les résultats
          </Button>
        </CardContent>
      </Card>

      <DangerConfirm
        open={ouvert}
        onOpenChange={setOuvert}
        titre="Purger tous les résultats ?"
        description={
          <>
            Cette action est <strong>irréversible</strong>. Les épreuves et leurs
            sources restent en base : un rescrape pourra les réimporter aussitôt.
          </>
        }
        motDeConfirmation={MOT_DE_CONFIRMATION}
        actionBloquee={!impact.data}
        libelleAction="Purger définitivement"
        enAttente={purge.isPending}
        onConfirm={confirmer}
      >
        {impact.isLoading && <Skeleton className="h-16 w-full" />}

        {impact.error && (
          <p className="text-sm text-destructive">
            L&apos;ampleur de la purge n&apos;a pas pu être chiffrée. Par prudence,
            la purge n&apos;est pas activée — réessayez plus tard.
          </p>
        )}

        {impact.data && (
          <ul className="space-y-1 text-sm">
            <li>
              <strong>{impact.data.participations}</strong>{" "}
              {plural(impact.data.participations, "résultat sera détruit", "résultats seront détruits")}.
            </li>
            <li>
              <strong>{impact.data.athletes}</strong>{" "}
              {plural(impact.data.athletes, "fiche athlète sera retirée", "fiches athlète seront retirées")}.
            </li>
          </ul>
        )}
      </DangerConfirm>
    </>
  );
}
