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
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { GroupDetailDialog } from "@/components/admin/GroupDetailDialog";
import { useCreateGroup, useDeleteGroup, useGroups } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { Group } from "@/lib/types";

/**
 * Ce que dit un refus ici : sans distinction, l'écran laisserait croire que le
 * club n'a organisé personne — un Codir vide plutôt qu'un Codir qu'on n'a pas
 * le droit de lire.
 */
const REFUS = { sujet: "groupes", action: "consulter les groupes d'appartenance" };

export function GroupsTable() {
  const { data, isLoading, error } = useGroups();
  const session = useSession();
  const creer = useCreateGroup();
  const supprimer = useDeleteGroup();
  const [nom, setNom] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  // Le groupe dont on regarde la composition. `null` = aucune modale ouverte ;
  // l'objet plutôt que l'identifiant, pour intituler la modale avant que son
  // détail soit arrivé.
  const [ouvert, setOuvert] = useState<Group | null>(null);

  // Confort d'affichage seul : chaque ressource porte sa garde côté API. Ne pas
  // proposer un geste qui rendrait 403 est tout ce qui se joue ici.
  const peutEcrire = session.data?.permissions.includes("groups:write") ?? false;

  async function soumettre(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!nom.trim() || !slug.trim()) return;
    try {
      await creer.mutateAsync({
        slug: slug.trim(),
        name: nom.trim(),
        description: description.trim(),
      });
      setNom("");
      setSlug("");
      setDescription("");
      toast.success("Groupe créé. Il naît vide.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function detruire(groupe: Group) {
    // Aucune confirmation : l'API refuse de supprimer un groupe peuplé, donc le
    // geste ne détruit jamais de composition. Rien n'est perdu, rien n'est à
    // confirmer — à l'inverse du retrait d'une adresse autorisée (#170).
    try {
      await supprimer.mutateAsync(groupe.id);
      toast.success(`« ${groupe.name} » a été supprimé.`);
    } catch (e) {
      // Le 409 du groupe encore peuplé porte son message côté serveur, déjà en
      // français, et il nomme le nombre de membres.
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {peutEcrire && (
        <form onSubmit={soumettre} className="flex flex-wrap items-end gap-2">
          <div className="space-y-1.5">
            <Label htmlFor="groupe-nom">Nom du groupe</Label>
            <Input
              id="groupe-nom"
              className="w-56"
              required
              placeholder="Comité de direction"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="groupe-slug">Identifiant</Label>
            {/* Fixé une fois pour toutes à la création : il ne se renomme pas.
                Le `pattern` est celui du backend — la validation native évite un
                aller-retour pour un 422 prévisible. */}
            <Input
              id="groupe-slug"
              className="w-40"
              required
              placeholder="codir"
              pattern="[a-z][a-z0-9-]*"
              title="Minuscules, chiffres et tirets, commençant par une lettre."
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="groupe-description">Description</Label>
            <Input
              id="groupe-description"
              placeholder="À quoi correspond ce groupe ?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={creer.isPending}>
            Créer le groupe
          </Button>
        </form>
      )}

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDeRefus(error, REFUS)} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Aucun groupe"
          description="Un groupe dit à quoi on appartient — le Codir, les officiels, une section. Il n'accorde aucun droit."
        />
      ) : (
        <Card className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Groupe</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Membres</TableHead>
                <TableHead>Créé le</TableHead>
                <TableHead className="sr-only">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((groupe) => (
                <TableRow key={groupe.id}>
                  <TableCell>
                    <Button
                      variant="link"
                      className="h-auto p-0 font-medium"
                      onClick={() => setOuvert(groupe)}
                    >
                      {groupe.name}
                    </Button>
                    <div className="text-muted-foreground text-xs">{groupe.slug}</div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {groupe.description || "—"}
                  </TableCell>
                  <TableCell>{groupe.member_count}</TableCell>
                  <TableCell>{formatDate(groupe.created_at)}</TableCell>
                  <TableCell className="text-right">
                    {peutEcrire && (
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Supprimer le groupe ${groupe.name}`}
                        onClick={() => detruire(groupe)}
                        // Bornée à **cette** ligne : `isPending` seul griserait
                        // tous les boutons du tableau pendant une suppression.
                        disabled={supprimer.isPending && supprimer.variables === groupe.id}
                      >
                        Supprimer
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {ouvert && (
        <GroupDetailDialog
          group={ouvert}
          open
          onOpenChange={(o) => !o && setOuvert(null)}
        />
      )}
    </div>
  );
}
