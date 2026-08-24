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
  useRevokeSessions,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { useRolesAttribuables } from "@/lib/roles";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { AllowedEmail } from "@/lib/types";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";

/**
 * Ce que dit un refus ici : sans distinction, l'écran mentirait sur *qui a accès
 * au back-office* — on en conclurait que personne n'est autorisé, la lecture la
 * plus alarmante possible d'un simple manque de droit.
 */
const REFUS = { sujet: "accès", action: "gérer les accès au back-office" };

export function AllowedEmailsTable() {
  const { data, isLoading, error } = useAllowedEmails();
  const ajouter = useAddAllowedEmail();
  const retirer = useRemoveAllowedEmail();
  const revoquer = useRevokeSessions();
  const session = useSession();
  const confirmerLeDanger = useDangerConfirm();
  // L'écran s'ouvre avec `allowed_emails:manage` seul : un bouton qui rendrait
  // 403 à chaque clic est pire que pas de bouton. Patron de `CoursesAdminTable`.
  const peutRevoquer = session.data?.permissions.includes("sessions:revoke") ?? false;
  const { roles, accordable, peutAttribuer } = useRolesAttribuables();
  const [saisie, setSaisie] = useState("");
  // Chaîne et non nombre : c'est la valeur d'un `<option>`, et « aucun » a
  // besoin d'être représentable.
  const [role, setRole] = useState("");
  // « Aucun » choisi **lève** le rôle posé ; sélecteur jamais touché ne se
  // prononce pas. Sans cette distinction, ré-autoriser une adresse — le geste
  // documenté pour rouvrir un compte fermé — effacerait en silence le rôle qui
  // l'attendait. C'est la sentinelle du service, côté écran.
  const [roleTouche, setRoleTouche] = useState(false);

  async function soumettre(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    const adresse = saisie.trim();
    if (!adresse) return;
    try {
      await ajouter.mutateAsync({
        email: adresse,
        // `undefined` **omet** le champ, ce que le backend distingue de `null` :
        // le premier ne se prononce pas sur le rôle, le second lève celui qui
        // était posé — et lever est un geste d'attribution comme un autre.
        roleId:
          peutAttribuer && roleTouche ? (role ? Number(role) : null) : undefined,
      });
      setSaisie("");
      setRole("");
      setRoleTouche(false);
      toast.success("Adresse autorisée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function supprimer(acces: AllowedEmail) {
    // Geste destructif : il ferme un accès et coupe les sessions vivantes. Le
    // dialog du produit et non le `confirm` du navigateur (#499) — ce dernier
    // n'est ni traduisible, ni stylable, ni testable au même titre.
    if (
      !(await confirmerLeDanger({
        titre: `Retirer « ${acces.email} » ?`,
        description: "Ses sessions ouvertes seront fermées immédiatement.",
        libelleAction: "Retirer",
      }))
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

  async function fermerLesSessions(acces: AllowedEmail) {
    try {
      const bilan = await revoquer.mutateAsync(acces.email);
      toast.success(
        `${bilan.sessions} session(s) fermée(s) sur ${bilan.accounts} compte(s).`,
      );
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {/* `flex-col`/`sm:flex-row` : sur 375 px, le champ e-mail était écrasé
          contre un `<select>` en `w-48` fixe (#479, ADM-11) — même schéma que
          `BenevoleAccessConfig.tsx`. */}
      <form onSubmit={soumettre} className="flex flex-col gap-3 sm:flex-row sm:items-end">
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
        {peutAttribuer && (
          <div className="space-y-1.5">
            <Label htmlFor="role-initial">Rôle à l&apos;inscription</Label>
            <select
              id="role-initial"
              className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm sm:w-48"
              value={role}
              onChange={(e) => {
                setRole(e.target.value);
                setRoleTouche(true);
              }}
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
        )}
        <Button type="submit" disabled={ajouter.isPending}>
          Ajouter
        </Button>
      </form>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDeRefus(error, REFUS)} />
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
                      <span className="text-[var(--tcn-text-faint)]">—</span>
                    )}
                  </TableCell>
                  <TableCell>{formatDate(acces.created_at)}</TableCell>
                  <TableCell>{acces.created_by_name ?? "—"}</TableCell>
                  <TableCell className="space-x-2 text-right">
                    {/* Sans confirmation, à l'inverse du retrait : le geste se
                        répare par une reconnexion. Il **supprime** les jetons,
                        là où retirer l'adresse se contente de les faire refuser
                        — réversiblement, dans la fenêtre de TTL. Offert sur les
                        seules adresses venues : sans compte, il n'y a rien à
                        fermer. */}
                    {peutRevoquer && acces.has_account && (
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Fermer les sessions de ${acces.email}`}
                        onClick={() => fermerLesSessions(acces)}
                        disabled={
                          revoquer.isPending && revoquer.variables === acces.email
                        }
                      >
                        Fermer les sessions
                      </Button>
                    )}
                    {/* `destructive` et son voisin neutre : le geste le plus
                        grave des deux était jusqu'ici le moins signalé (#499,
                        ADM-8). Fermer les sessions se répare par une
                        reconnexion, retirer l'adresse non. */}
                    <Button
                      size="sm"
                      variant="destructive"
                      aria-label={`Retirer l'accès de ${acces.email}`}
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
