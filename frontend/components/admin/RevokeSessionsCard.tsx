"use client";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { ApiError } from "@/lib/api/client";
import { useRevokeSessions } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

/**
 * Le geste d'incident (#169) : fermer d'un coup toutes les sessions ouvertes.
 *
 * Vit au bas de « Accès au back-office », sous la liste : c'est le même écran
 * qui porte la révocation **par adresse**, ligne par ligne. Les séparer aurait
 * demandé une entrée de navigation pour un unique bouton.
 *
 * La session de l'opérateur tombe avec les autres, et le dialogue le dit avant :
 * sous fuite, son jeton est suspect comme les autres. D'où la redirection vers
 * `/login` au succès — laisser un écran d'apparence connectée alors que la
 * requête suivante rendra 401 serait un mensonge d'interface.
 *
 * L'écran s'ouvre avec `allowed_emails:manage` seul, quand la route exige
 * `sessions:revoke` : sans ce pouvoir la carte ne s'affiche pas du tout, comme
 * son bouton frère par adresse dans `AllowedEmailsTable`. Rien à dire ici sur la
 * consultation — l'écran reste pleinement agissant sur les adresses, seule cette
 * carte-là s'efface, et une carte bordée de rouge sans son bouton n'expliquerait
 * pas mieux qu'elle ne troublerait.
 */
export function RevokeSessionsCard() {
  const router = useRouter();
  const revoquer = useRevokeSessions();
  const session = useSession();
  const confirmerLeDanger = useDangerConfirm();
  const peutRevoquer = session.data?.permissions.includes("sessions:revoke") ?? false;

  async function fermer() {
    // Geste destructif malgré un rayon d'action réparable : il déconnecte tout
    // le monde, l'opérateur compris (#499). Le dialog du produit et non le
    // `confirm` du navigateur — ce dernier n'est ni traduisible, ni stylable,
    // ni testable au même titre.
    if (
      !(await confirmerLeDanger({
        titre: "Fermer toutes les sessions ?",
        description:
          "Toutes les sessions ouvertes seront fermées, la vôtre comprise : vous serez renvoyé vers la page de connexion. Les comptes restent actifs, chacun peut se reconnecter aussitôt.",
        libelleAction: "Révoquer",
      }))
    ) {
      return;
    }
    try {
      // Sans adresse : la portée est globale.
      const bilan = await revoquer.mutateAsync(undefined);
      toast.success(
        `${bilan.sessions} session(s) fermée(s) sur ${bilan.accounts} compte(s).`,
      );
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
        router.push("/login");
      }
    }
  }

  if (!peutRevoquer) return null;

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle>Révocation d&apos;urgence</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Après une fuite de jetons, un poste perdu ou un doute sur la base :
          ferme toutes les sessions ouvertes, tous comptes confondus. Personne
          n&apos;est désactivé — chacun se reconnecte normalement.
        </p>
        <Button variant="destructive" onClick={fermer} disabled={revoquer.isPending}>
          Fermer toutes les sessions
        </Button>
      </CardContent>
    </Card>
  );
}
