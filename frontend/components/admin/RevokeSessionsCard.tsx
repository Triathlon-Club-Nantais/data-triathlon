"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
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
import { ApiError } from "@/lib/api/client";
import { useRevokeAllSessions } from "@/lib/queries/admin";

/**
 * Le geste d'incident (#169) : fermer d'un coup toutes les sessions ouvertes.
 *
 * **Globale, et uniquement globale.** Fermer les sessions d'un compte a déjà son
 * geste — retirer son adresse dans « Accès au back-office » (#170).
 *
 * La session de l'opérateur tombe avec les autres, et le dialogue le dit avant :
 * sous fuite, son jeton est suspect comme les autres. D'où la redirection vers
 * `/login` au succès — laisser un écran d'apparence connectée alors que la
 * requête suivante rendra 401 serait un mensonge d'interface.
 */
export function RevokeSessionsCard() {
  const [ouvert, setOuvert] = useState(false);
  const router = useRouter();
  const revoquer = useRevokeAllSessions();

  async function confirmer() {
    try {
      const bilan = await revoquer.mutateAsync();
      toast.success(
        `${bilan.sessions} session(s) fermée(s) sur ${bilan.accounts} compte(s).`,
      );
      setOuvert(false);
      router.push("/login");
    } catch (e) {
      // Le message du serveur est déjà en français ; en inventer un second le
      // contredirait le jour où il précise la cause.
      toast.error((e as Error).message);
      // Un 401 ici n'est pas un refus : la révocation a pu **aboutir** et la
      // réponse se perdre (réveil à froid, 502, onglet fermé) — le jeton de
      // l'appelant est alors mort, et tout réessai rendra 401 sans jamais dire
      // « déjà fait ». Rester sur un écran d'apparence connectée en annonçant
      // un échec serait le pire des deux mensonges.
      if (e instanceof ApiError && e.status === 401) {
        setOuvert(false);
        router.push("/login");
      }
    }
  }

  return (
    <>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Révocation d&apos;urgence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground text-sm">
            Après une fuite de jetons, un poste perdu ou un doute sur la base :
            ferme toutes les sessions ouvertes, tous comptes confondus. Personne
            n&apos;est désactivé — chacun se reconnecte normalement.
          </p>
          <Button variant="destructive" onClick={() => setOuvert(true)}>
            Fermer toutes les sessions
          </Button>
        </CardContent>
      </Card>

      <Dialog open={ouvert} onOpenChange={setOuvert}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Fermer toutes les sessions ?</DialogTitle>
            <DialogDescription>
              Toutes les sessions ouvertes seront fermées, la vôtre comprise :
              vous serez renvoyé vers la page de connexion. Les comptes restent
              actifs, chacun peut se reconnecter aussitôt.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOuvert(false)}>
              Renoncer
            </Button>
            <Button
              variant="destructive"
              onClick={confirmer}
              disabled={revoquer.isPending}
            >
              Révoquer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
