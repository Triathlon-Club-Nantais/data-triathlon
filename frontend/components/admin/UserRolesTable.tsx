"use client";
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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  useAdminUsers,
  useGrantRole,
  useRevokeRole,
  useRevokeUserSessions,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { useRolesAttribuables } from "@/lib/roles";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { AdminUser, SessionRole } from "@/lib/types";

/**
 * Ce que dit un refus ici : sans distinction, l'écran laisserait croire que
 * **personne** n'a de compte, c'est-à-dire que le club n'a aucun administrateur.
 */
const REFUS = { sujet: "utilisateurs", action: "consulter les utilisateurs" };

export function UserRolesTable() {
  const { data, isLoading, error } = useAdminUsers();
  const { roles, accordable } = useRolesAttribuables();
  const attribuer = useGrantRole();
  const retirer = useRevokeRole();
  const session = useSession();
  const revoquer = useRevokeUserSessions();
  // L'écran est atteignable avec `roles:assign` seul : un bouton qui rendrait
  // 403 à chaque clic est pire que pas de bouton. Patron de `CoursesAdminTable`.
  const peutRevoquer = session.data?.permissions.includes("sessions:revoke") ?? false;

  async function poser(utilisateur: AdminUser, roleId: number) {
    try {
      await attribuer.mutateAsync({ userId: utilisateur.id, roleId });
      toast.success("Rôle attribué.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function oter(utilisateur: AdminUser, role: SessionRole) {
    try {
      await retirer.mutateAsync({ userId: utilisateur.id, roleId: role.id });
      toast.success("Rôle retiré.");
    } catch (e) {
      // Le 409 du dernier administrateur porte son message côté serveur, déjà
      // en français ; le front le rend tel quel plutôt que d'en inventer un
      // second, et la liste reste inchangée.
      toast.error((e as Error).message);
    }
  }

  async function fermerLesSessions(utilisateur: AdminUser) {
    try {
      const bilan = await revoquer.mutateAsync(utilisateur.id);
      toast.success(
        `${bilan.sessions} session(s) fermée(s) pour ${utilisateur.display_name}.`,
      );
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="Aucun utilisateur"
        description="Un compte naît de la première connexion réussie d'une adresse autorisée."
      />
    );
  }

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Utilisateur</TableHead>
            <TableHead>Rôles</TableHead>
            <TableHead>Attribuer</TableHead>
            <TableHead>Inscrit le</TableHead>
            {peutRevoquer && <TableHead>Sessions</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((utilisateur) => {
            const disponibles = roles.filter(
              (role) => !utilisateur.roles.some((porte) => porte.id === role.id),
            );
            return (
              <TableRow key={utilisateur.id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div>
                      <div className="font-medium">{utilisateur.display_name}</div>
                      <div className="text-muted-foreground text-xs">
                        {utilisateur.email}
                      </div>
                    </div>
                    {!utilisateur.is_active && (
                      // Effet d'un retrait de la liste d'autorisation (#170) :
                      // le compte et ses rôles survivent, la connexion non.
                      <Badge variant="destructive">Désactivé</Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {utilisateur.roles.length === 0 ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {utilisateur.roles.map((role) => (
                        <Badge key={role.id} variant="secondary" className="gap-1 pr-1">
                          {role.name}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="size-4 rounded-full p-0 text-xs"
                            aria-label={`Retirer le rôle ${role.name} de ${utilisateur.display_name}`}
                            onClick={() => oter(utilisateur, role)}
                          >
                            ×
                          </Button>
                        </Badge>
                      ))}
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  {/* `<select>` natif : un rôle par ligne, clavier et lecteur
                      d'écran compris, sans état local — la valeur retombe sur
                      le libellé dès que la liste se rafraîchit. */}
                  <select
                    aria-label={`Attribuer un rôle à ${utilisateur.display_name}`}
                    className="border-input h-9 rounded-md border bg-transparent px-2 text-sm"
                    value=""
                    disabled={disponibles.length === 0}
                    onChange={(e) => poser(utilisateur, Number(e.target.value))}
                  >
                    <option value="" disabled>
                      Ajouter un rôle…
                    </option>
                    {disponibles.map((role) => (
                      <option
                        key={role.id}
                        value={role.id}
                        disabled={!accordable(role)}
                      >
                        {role.name}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell>{formatDate(utilisateur.created_at)}</TableCell>
                {peutRevoquer && (
                  <TableCell>
                    {/* Sans dialogue de confirmation, comme la CLI sur
                        `--email` : le geste se répare par une reconnexion, à
                        l'inverse de la révocation globale. Il **supprime** les
                        jetons, là où retirer l'adresse (#170) se contente de
                        les faire refuser — réversiblement. */}
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={revoquer.isPending}
                      aria-label={`Fermer les sessions de ${utilisateur.display_name}`}
                      onClick={() => fermerLesSessions(utilisateur)}
                    >
                      Fermer les sessions
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
