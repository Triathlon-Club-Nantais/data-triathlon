"use client";
import { useState } from "react";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  useAllowedEmails,
  useAddAllowedEmail,
  useRemoveAllowedEmail,
} from "@/lib/queries/admin";
import { useRolesAttribuables } from "@/lib/roles";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/date";
import type { AllowedEmail } from "@/lib/types";

/**
 * Ce qu'un refus doit dire, et qu'une liste vide ne doit pas dire.
 *
 * Même défaut que celui fermé sur `PendingProvidersTable` : sur un 403, `data`
 * est `undefined`. Ici l'écran mentirait sur *qui a accès au back-office* — on
 * en conclurait que personne n'est autorisé, ce qui est la lecture la plus
 * alarmante possible d'un simple manque de droit.
 */
function messageDErreur(erreur: Error): { title: string; description: string } {
  const statut = erreur instanceof ApiError ? erreur.status : 0;
  if (statut === 401) {
    return {
      title: "Session expirée",
      description: "Reconnectez-vous pour consulter les accès.",
    };
  }
  if (statut === 403) {
    return {
      title: "Accès refusé",
      description:
        "Votre rôle ne permet pas de gérer les accès au back-office. " +
        "Demandez le pouvoir correspondant à un administrateur.",
    };
  }
  return {
    title: "Liste indisponible",
    description: "Les accès n'ont pas pu être chargés. Réessayez plus tard.",
  };
}

export function AllowedEmailsTable() {
  const { data, isLoading, error } = useAllowedEmails();
  const ajouter = useAddAllowedEmail();
  const retirer = useRemoveAllowedEmail();
  const { roles, accordable } = useRolesAttribuables();
  const [saisie, setSaisie] = useState("");
  // Chaîne et non nombre : c'est la valeur d'un `<option>`, et « aucun » a
  // besoin d'être représentable.
  const [role, setRole] = useState("");

  async function soumettre(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    const adresse = saisie.trim();
    if (!adresse) return;
    try {
      await ajouter.mutateAsync({
        email: adresse,
        roleId: role ? Number(role) : null,
      });
      setSaisie("");
      setRole("");
      toast.success("Adresse autorisée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function supprimer(acces: AllowedEmail) {
    // Geste destructif : il coupe des sessions vivantes. Réversible par une
    // réinscription, mais pas silencieux — d'où la confirmation native plutôt
    // qu'une boîte de dialogue maison.
    if (
      !window.confirm(
        `Retirer « ${acces.email} » ? Ses sessions ouvertes seront fermées immédiatement.`,
      )
    ) {
      return;
    }
    try {
      await retirer.mutateAsync(acces.id);
      toast.success("Adresse retirée. L'accès est fermé immédiatement.");
    } catch (e) {
      // Le 409 du dernier administrateur porte son message côté serveur ; le
      // front le rend tel quel plutôt que d'en inventer un second.
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={soumettre} className="flex items-end gap-2">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="adresse-autorisee">Adresse à autoriser</Label>
          <Input
            id="adresse-autorisee"
            type="email"
            placeholder="prenom.nom@exemple.fr"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
          />
        </div>
        {/* Le rôle vit sur l'autorisation, pas sur la personne : il dit avec
            quoi le compte naîtra à sa **première** connexion (#239). Sans lui,
            le geste d'administration était coupé en deux par un événement que
            l'administrateur ne contrôle pas. */}
        <div className="space-y-1.5">
          <Label htmlFor="role-initial">Rôle à l&apos;inscription</Label>
          <select
            id="role-initial"
            className="border-input h-9 w-48 rounded-md border bg-transparent px-2 text-sm"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="">Aucun</option>
            {roles.map((disponible) => (
              <option
                key={disponible.id}
                value={disponible.id}
                disabled={!accordable(disponible)}
              >
                {disponible.name}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" disabled={ajouter.isPending}>
          Ajouter
        </Button>
      </form>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDErreur(error)} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Aucune adresse autorisée"
          description="Tant que cette liste est vide, personne ne peut ouvrir de session."
        />
      ) : (
        <Card className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Adresse</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Rôle à l&apos;inscription</TableHead>
                <TableHead>Ajoutée le</TableHead>
                <TableHead>Par</TableHead>
                <TableHead className="sr-only">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((acces) => (
                <TableRow key={acces.id}>
                  <TableCell>{acces.email}</TableCell>
                  {/* Autorisée ≠ venue : tant que la personne ne s'est pas
                      connectée, aucun compte n'existe (#114, FR-003) et le rôle
                      ci-contre n'est pas encore appliqué. C'est le seul retour
                      qu'on ait dessus. */}
                  <TableCell>
                    {acces.has_account ? (
                      <Badge variant="secondary">Compte actif</Badge>
                    ) : (
                      <Badge variant="outline">Jamais connecté</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {acces.role ? (
                      <Badge variant="secondary">{acces.role.name}</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>{formatDate(acces.created_at)}</TableCell>
                  <TableCell>{acces.created_by_name ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => supprimer(acces)}
                      // Bornée à **cette** ligne : `isPending` seul grisait
                      // tous les boutons du tableau pendant un retrait.
                      disabled={retirer.isPending && retirer.variables === acces.id}
                    >
                      Retirer
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
