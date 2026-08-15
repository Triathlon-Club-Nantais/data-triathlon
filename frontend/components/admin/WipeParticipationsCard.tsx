"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useParticipationsWipeImpact, useWipeAllParticipations } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

//: Le mot à taper pour activer la confirmation — la portée est la base
//: entière, pas une épreuve, d'où ce garde-fou renforcé par rapport à
//: `DeleteCourseDialog` (#384).
const MOT_DE_CONFIRMATION = "SUPPRIMER";

/**
 * Repartir d'une base de résultats propre (#384) — par exemple avant un
 * rescrape complet suite à un changement de logique d'import.
 *
 * Vit au bas de `/admin/courses`, sur le patron de `RevokeSessionsCard` :
 * un unique bouton ne justifie pas un écran ni une entrée de navigation
 * dédiés. `Course` et `course_sources` restent intacts — c'est ce qui rend
 * un rescrape possible juste après, sans tout réimporter depuis les URLs
 * sources.
 *
 * **Le serveur reste seul juge** (FR-009 du domaine #115) : ce test de
 * pouvoir n'autorise rien, il évite de proposer un bouton qui rendrait 403.
 */
export function WipeParticipationsCard() {
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState("");
  const session = useSession();
  const impact = useParticipationsWipeImpact(ouvert);
  const purge = useWipeAllParticipations();

  const peutPurger = session.data?.permissions.includes("participations:wipe_all") ?? false;
  if (!peutPurger) return null;

  function fermer(prochain: boolean) {
    setOuvert(prochain);
    if (!prochain) setSaisie("");
  }

  async function confirmer() {
    try {
      await purge.mutateAsync();
      toast.success("Tous les résultats ont été supprimés.");
      fermer(false);
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
            restent intactes ; seuls les résultats et les fiches coureur qu&apos;ils
            laissent vides sont détruits.
          </p>
          <Button variant="destructive" onClick={() => setOuvert(true)}>
            Purger tous les résultats
          </Button>
        </CardContent>
      </Card>

      <Dialog open={ouvert} onOpenChange={fermer}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Purger tous les résultats ?</DialogTitle>
            <DialogDescription>
              Cette action est <strong>irréversible</strong>. Les épreuves et leurs
              sources restent en base : un rescrape pourra les réimporter aussitôt.
            </DialogDescription>
          </DialogHeader>

          {impact.isLoading && <Skeleton className="h-16 w-full" />}

          {impact.error && (
            <p className="text-sm text-destructive">
              L&apos;ampleur de la purge n&apos;a pas pu être chiffrée. Par prudence,
              la purge n&apos;est pas proposée — réessayez plus tard.
            </p>
          )}

          {impact.data && (
            <>
              <ul className="space-y-1 text-sm">
                <li>
                  <strong>{impact.data.participations}</strong> résultat
                  {impact.data.participations === 1 ? " sera détruit" : "s seront détruits"}.
                </li>
                <li>
                  <strong>{impact.data.athletes}</strong> fiche
                  {impact.data.athletes === 1
                    ? " coureur sera retirée"
                    : "s coureur seront retirées"}
                  .
                </li>
              </ul>
              <label className="block space-y-1 text-sm" htmlFor="wipe-confirm-input">
                Tapez <strong>{MOT_DE_CONFIRMATION}</strong> pour activer la confirmation.
                <Input
                  id="wipe-confirm-input"
                  value={saisie}
                  onChange={(e) => setSaisie(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
            </>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => fermer(false)}>
              Renoncer
            </Button>
            {impact.data && (
              <Button
                variant="destructive"
                onClick={confirmer}
                disabled={purge.isPending || saisie !== MOT_DE_CONFIRMATION}
              >
                Purger définitivement
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
