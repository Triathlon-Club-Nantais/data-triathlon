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
import { useCoursesWipeImpact, useWipeAllCourses } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

//: Même garde-fou que `WipeParticipationsCard` — la portée ici est encore
//: plus large (le catalogue entier), d'où le même mot à taper (#384, suite).
const MOT_DE_CONFIRMATION = "SUPPRIMER";

/**
 * Vider le catalogue d'épreuves entier — sources et résultats compris (#384,
 * suite). Strictement plus destructeur que `WipeParticipationsCard` : là où
 * celui-ci garde `Course`/`course_sources` pour permettre un rescrape
 * immédiat, ce geste-ci les emporte aussi — reconstituer le catalogue exige
 * de recoller chaque URL depuis zéro.
 *
 * Carte séparée, volontairement : mélanger deux chiffrages différents dans
 * un même dialog de confirmation serait confus. Même patron que
 * `WipeParticipationsCard` sinon (chiffrage affiché, mot à taper, aucune
 * annulation possible).
 *
 * **Le serveur reste seul juge** (FR-009 du domaine #115) : ce test de
 * pouvoir n'autorise rien, il évite de proposer un bouton qui rendrait 403.
 */
export function WipeCoursesCard() {
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState("");
  const session = useSession();
  const impact = useCoursesWipeImpact(ouvert);
  const purge = useWipeAllCourses();

  const peutPurger = session.data?.permissions.includes("courses:wipe_all") ?? false;
  if (!peutPurger) return null;

  function fermer(prochain: boolean) {
    setOuvert(prochain);
    if (!prochain) setSaisie("");
  }

  async function confirmer() {
    try {
      await purge.mutateAsync();
      toast.success("Toutes les épreuves ont été supprimées.");
      fermer(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Repartir de zéro</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Vide entièrement le catalogue — épreuves, sources et résultats compris.
            Contrairement à la purge des résultats seule, les épreuves ne pourront
            pas être re-scrapées automatiquement : il faudra recoller chaque URL.
          </p>
          <Button variant="destructive" onClick={() => setOuvert(true)}>
            Supprimer toutes les épreuves
          </Button>
        </CardContent>
      </Card>

      <Dialog open={ouvert} onOpenChange={fermer}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer toutes les épreuves ?</DialogTitle>
            <DialogDescription>
              Cette action est <strong>irréversible</strong>, et va plus loin que la
              purge des résultats : les épreuves et leurs sources disparaissent aussi.
              Il faudra recoller chaque URL pour reconstituer le catalogue.
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
                  <strong>{impact.data.courses}</strong> épreuve
                  {impact.data.courses === 1 ? " sera détruite" : "s seront détruites"}.
                </li>
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
              <label className="block space-y-1 text-sm" htmlFor="wipe-courses-confirm-input">
                Tapez <strong>{MOT_DE_CONFIRMATION}</strong> pour activer la confirmation.
                <Input
                  id="wipe-courses-confirm-input"
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
                Supprimer définitivement
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
