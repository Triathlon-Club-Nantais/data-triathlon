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
import { useAdminUsers, useGrantRole, useRevokeRole } from "@/lib/queries/admin";
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
  // `users:read` ouvre la liste ; les deux écritures — `POST` et
  // `DELETE /admin/users/{id}/roles` — exigent `roles:assign`, attribuable
  // séparément. `useRolesAttribuables` répond déjà à la question, pour les deux
  // guichets qui la posent : la poser une seconde fois ici les ferait diverger.
  const { roles, accordable, peutAttribuer } = useRolesAttribuables();
  const attribuer = useGrantRole();
  const retirer = useRevokeRole();

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
    <div className="space-y-4">
      {/* Un écran privé de ses deux contrôles ressemble à un écran cassé : la
          phrase dit lequel des deux manque, plutôt que de laisser deviner.
          Même formulation que `RolePermissionsEditor`, même libellé de pouvoir
          que l'inventaire de `core/permissions.py`. */}
      {!peutAttribuer && (
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Cet écran est en consultation : attribuer ou retirer un rôle demande le pouvoir
          « Attribuer les rôles ».
        </p>
      )}
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Utilisateur</TableHead>
              <TableHead>Rôles</TableHead>
              {peutAttribuer && <TableHead>Attribuer</TableHead>}
              <TableHead>Inscrit le</TableHead>
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
                        <div className="text-[var(--tcn-text-faint)] text-xs">
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
                      <span className="text-[var(--tcn-text-faint)]">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {utilisateur.roles.map((role) => (
                          <Badge key={role.id} variant="secondary" className="gap-1 pr-1">
                            {role.name}
                            {peutAttribuer && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="size-4 rounded-full p-0 text-xs"
                                aria-label={`Retirer le rôle ${role.name} de ${utilisateur.display_name}`}
                                onClick={() => oter(utilisateur, role)}
                              >
                                ×
                              </Button>
                            )}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  {peutAttribuer && (
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
                  )}
                  <TableCell>{formatDate(utilisateur.created_at)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
