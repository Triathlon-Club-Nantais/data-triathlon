"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAddGroupMember,
  useAdminUsers,
  useGroup,
  useRemoveGroupMember,
  useUpdateGroup,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import type { Group, GroupMember } from "@/lib/types";

/**
 * La composition d'un groupe, et son libellé (#241).
 *
 * **Un groupe n'accorde rien** : rien ici ne parle de droits, et l'écran ne
 * voisine avec aucune composition de rôle. Ce qu'il montre est une
 * appartenance — sans imbrication ni date de fin, aucune des deux n'existant
 * dans le modèle.
 *
 * Le renommage vit ici plutôt que dans la liste : c'est la même ressource que
 * la composition, et `PATCH` en rend le détail.
 */
export function GroupDetailDialog({
  group,
  open,
  onOpenChange,
}: {
  group: Group;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const detail = useGroup(open ? group.id : null);
  const utilisateurs = useAdminUsers();
  const session = useSession();
  const modifier = useUpdateGroup();
  const ajouter = useAddGroupMember();
  const retirer = useRemoveGroupMember();
  // Semés depuis la liste, qui porte déjà les deux : attendre le détail pour
  // remplir un formulaire qu'on sait déjà remplir ferait clignoter les champs.
  const [nom, setNom] = useState(group.name);
  const [description, setDescription] = useState(group.description);

  const peutEcrire = session.data?.permissions.includes("groups:write") ?? false;
  const peutAssigner = session.data?.permissions.includes("groups:assign") ?? false;

  const membres = detail.data?.members ?? [];
  const ajoutables = (utilisateurs.data ?? []).filter(
    (utilisateur) => !membres.some((membre) => membre.user_id === utilisateur.id),
  );

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    try {
      await modifier.mutateAsync({ id: group.id, champs: { name: nom, description } });
      toast.success("Groupe modifié.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function ajouterMembre(userId: number) {
    try {
      await ajouter.mutateAsync({ groupId: group.id, userId });
      toast.success("Membre ajouté.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function retirerMembre(membre: GroupMember) {
    // Sans confirmation, délibérément : retirer quelqu'un d'un groupe ne coupe
    // aucune session et ne lui ôte aucun droit — le geste se refait d'un clic.
    // Le retrait d'une adresse autorisée (#170), lui, ferme un accès : les deux
    // ne doivent pas se ressembler.
    try {
      await retirer.mutateAsync({ groupId: group.id, userId: membre.user_id });
      toast.success("Membre retiré.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          {/* Le détail fait foi dès qu'il est là : la prop est un instantané
              pris au clic, et resterait sur l'ancien nom après un renommage —
              le geste qu'on vient de confirmer aurait l'air de n'avoir rien
              fait. Elle ne sert que de repli pendant le chargement. */}
          <DialogTitle>{detail.data?.name ?? group.name}</DialogTitle>
          <DialogDescription>
            Qui appartient à ce groupe. Une appartenance n&apos;accorde aucun droit et
            ne se termine pas d&apos;elle-même.
          </DialogDescription>
        </DialogHeader>

        {peutEcrire && (
          <form onSubmit={enregistrer} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="groupe-detail-nom">Nom</Label>
              <Input
                id="groupe-detail-nom"
                value={nom}
                onChange={(e) => setNom(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="groupe-detail-description">Description</Label>
              <Input
                id="groupe-detail-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <Button type="submit" size="sm" disabled={modifier.isPending}>
              Enregistrer
            </Button>
          </form>
        )}

        {peutAssigner && (
          <div className="space-y-1.5">
            <Label htmlFor="groupe-ajout-membre">Ajouter un membre</Label>
            {/* `<select>` natif, comme l'attribution d'un rôle : clavier et
                lecteur d'écran compris, sans état local — la valeur retombe sur
                le libellé dès que la composition se rafraîchit. */}
            <select
              id="groupe-ajout-membre"
              className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm"
              value=""
              disabled={ajoutables.length === 0}
              onChange={(e) => ajouterMembre(Number(e.target.value))}
            >
              <option value="" disabled>
                Choisir un utilisateur…
              </option>
              {ajoutables.map((utilisateur) => (
                <option key={utilisateur.id} value={utilisateur.id}>
                  {/* `display_name` vaut `""` par défaut en base et chez deux
                      fournisseurs d'identité : sans repli, l'option est vide et
                      ne peut pas être choisie sciemment. */}
                  {utilisateur.display_name || utilisateur.email}
                </option>
              ))}
            </select>
            {utilisateurs.error && (
              <p className="text-[var(--tcn-text-faint)] text-xs">
                La liste des utilisateurs n&apos;a pas pu être chargée : ajouter un
                membre demande aussi de pouvoir les consulter.
              </p>
            )}
          </div>
        )}

        {detail.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : detail.error ? (
          <p className="text-destructive text-sm">
            La composition de ce groupe n&apos;a pas pu être chargée. Réessayez plus
            tard.
          </p>
        ) : membres.length === 0 ? (
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Aucun membre. Un groupe existe avant d&apos;être peuplé.
          </p>
        ) : (
          <ul className="divide-border divide-y">
            {membres.map((membre) => {
              // Même repli que le sélecteur : un membre sans nom affiché reste
              // désignable, à l'écran comme au lecteur d'écran.
              const nom = membre.display_name || membre.email;
              return (
              <li
                key={membre.user_id}
                className="flex items-center justify-between gap-2 py-2"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{nom}</span>
                    {/* Un compte désactivé (#170) **reste** membre : rien de ce
                        que porte un groupe ne dépend de son activité. */}
                    {!membre.is_active && <Badge variant="destructive">Désactivé</Badge>}
                  </div>
                  <div className="text-[var(--tcn-text-faint)] text-xs">
                    <span>{membre.email}</span> · depuis le{" "}
                    {formatDate(membre.joined_at)}
                  </div>
                </div>
                {peutAssigner && (
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Retirer ${nom} du groupe`}
                    onClick={() => retirerMembre(membre)}
                  >
                    Retirer
                  </Button>
                )}
              </li>
              );
            })}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
