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
import { useSession } from "@/lib/queries/auth";
import { useRolesAttribuables } from "@/lib/roles";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
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
  const confirmerLeDanger = useDangerConfirm();
  const session = useSession();

  async function poser(utilisateur: AdminUser, roleId: number) {
    try {
      await attribuer.mutateAsync({ userId: utilisateur.id, roleId });
      toast.success("Rôle attribué.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function oter(utilisateur: AdminUser, role: SessionRole) {
    // Un retrait de rôle ôte des pouvoirs : il se confirme, nommément, comme le
    // retrait d'une adresse autorisée dont la gravité est comparable (#499,
    // ADM-9). Il partait jusqu'ici au premier clic, sans annulation.
    //
    // L'avertissement se borne à ce que le front sait avec certitude — « c'est
    // vous ». Le serveur, lui, refuse par un 409 que l'organisation perde son
    // dernier administrateur actif (`admin_roles.py:182`) : ce prédicat-là est
    // le sien, le recalculer ici le ferait diverger au premier ajustement.
    const cEstMoi = session.data?.id === utilisateur.id;
    if (
      !(await confirmerLeDanger({
        titre: `Retirer le rôle « ${role.name} » à « ${utilisateur.display_name} » ?`,
        description:
          "Les pouvoirs que ce rôle lui donnait ne s'appliqueront plus dès la requête suivante.",
        avertissement: cEstMoi ? (
          <>
            <strong>Ce rôle est le vôtre.</strong> Vous pourriez perdre l&apos;accès à cet écran.
          </>
        ) : undefined,
        libelleAction: "Retirer le rôle",
      }))
    ) {
      return;
    }
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
                          // `h-7` (28 px) : le badge grandit avec la croix — sans
                          // quoi `overflow-hidden` (badge, `h-5` par défaut) la
                          // retaillerait à sa taille d'origine, 16 px (#479).
                          <Badge key={role.id} variant="secondary" className="h-7 gap-1 pr-1">
                            {role.name}
                            {peutAttribuer && (
                              <Button
                                size="icon-xs"
                                variant="ghost"
                                // `ghost` au repos, `destructive` au survol et
                                // au focus : c'est la seule exception à la
                                // règle de couleur (#499), et elle tient à la
                                // densité — une croix par badge, plusieurs
                                // badges par ligne. En rouge permanent, plus
                                // rien ne ressort du tableau ; là, le rouge
                                // arrive au moment où l'on vise.
                                className="rounded-full p-0 text-xs hover:bg-destructive/10 hover:text-destructive focus-visible:bg-destructive/10 focus-visible:text-destructive"
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
