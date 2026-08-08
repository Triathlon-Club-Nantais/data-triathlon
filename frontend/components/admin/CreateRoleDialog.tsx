"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateRole } from "@/lib/queries/admin";
import type { PermissionGroup } from "@/lib/types";
import { PermissionGrid } from "./PermissionGrid";

/**
 * Le nom, ramené à la forme que le serveur exige : `^[a-z][a-z0-9-]*$`.
 *
 * `normalize("NFD")` sépare les accents de leur lettre, la classe `\p{Diacritic}`
 * les retire — « Bénévole » devient « benevole » sans table de correspondance.
 */
/** La contrainte de `RoleCreate.slug`, recopiée pour ne pas la découvrir en 422. */
const SLUG_ATTENDU = /^[a-z][a-z0-9-]*$/;

export function slugifier(nom: string): string {
  return nom
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/^[0-9-]+/, "");
}

/**
 * Créer un rôle (#240, US3).
 *
 * L'identifiant est **visible et prérempli**, pas fabriqué en silence : il est
 * fixé une fois pour toutes — `RoleUpdate` le refuse ensuite par
 * `extra="forbid"` — et il traverse `grant-role --role` et le semis. Le
 * découvrir après coup, c'est le découvrir trop tard.
 *
 * La composition initiale passe par la **même** grille que l'édition : l'écrire
 * deux fois ferait diverger le regroupement, qui est le cœur de l'écran.
 */
export function CreateRoleDialog({
  inventaire,
  disabledCodes,
  raison,
  open,
  onOpenChange,
}: {
  inventaire: PermissionGroup[];
  /**
   * Codes que la session ne porte pas. `create_role` passe à `assert_may_grant`
   * l'**ensemble complet** des codes demandés — pas une différence symétrique
   * comme `update_role` — donc une case laissée cochable ici est un 403 promis.
   */
  disabledCodes?: ReadonlySet<string>;
  raison?: string;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [nom, setNom] = useState("");
  const [slug, setSlug] = useState("");
  // Dès que l'identifiant est corrigé à la main, il cesse de suivre le nom :
  // le réécrire sous les doigts de qui vient de le choisir serait pire que de
  // ne rien proposer.
  const [slugCorrige, setSlugCorrige] = useState(false);
  const [description, setDescription] = useState("");
  const [codes, setCodes] = useState<ReadonlySet<string>>(new Set());

  const creation = useCreateRole();
  const slugValide = SLUG_ATTENDU.test(slug);

  function saisirLeNom(valeur: string) {
    setNom(valeur);
    if (!slugCorrige) setSlug(slugifier(valeur));
  }

  function reinitialiser() {
    setNom("");
    setSlug("");
    setSlugCorrige(false);
    setDescription("");
    setCodes(new Set());
  }

  async function creer() {
    try {
      await creation.mutateAsync({
        slug,
        name: nom.trim(),
        description,
        permissions: [...codes],
      });
      toast.success("Rôle créé.");
      reinitialiser();
      onOpenChange(false);
    } catch (e) {
      // Le 409 d'identifiant déjà pris porte son message côté serveur, et la
      // saisie reste : la refaire pour un identifiant à changer serait absurde.
      toast.error((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Créer un rôle</DialogTitle>
          <DialogDescription>
            Un rôle porte des pouvoirs. L&apos;identifiant est définitif : il sert en ligne de
            commande et ne se renomme pas.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="nouveau-role-nom">Nom du rôle</Label>
              <Input
                id="nouveau-role-nom"
                value={nom}
                onChange={(e) => saisirLeNom(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nouveau-role-slug">Identifiant</Label>
              <Input
                id="nouveau-role-slug"
                value={slug}
                aria-invalid={!slugValide}
                aria-describedby={slugValide ? undefined : "nouveau-role-slug-forme"}
                onChange={(e) => {
                  setSlugCorrige(true);
                  setSlug(e.target.value);
                }}
              />
              {/* Sans cette garde, un identifiant corrigé à la main revient en
                  « String should match pattern '^[a-z][a-z0-9-]*$' » — du
                  Pydantic anglais dans une interface française. Le cas d'un nom
                  sans lettre (« 42 ») passe ici aussi : le champ est vide, et
                  cette phrase dit enfin pourquoi le bouton ne fait rien. */}
              {!slugValide && (
                <p id="nouveau-role-slug-forme" className="text-sm text-muted-foreground">
                  L&apos;identifiant commence par une lettre minuscule, puis ne porte que des
                  minuscules, des chiffres ou des traits d&apos;union.
                </p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="nouveau-role-description">Description</Label>
            <Textarea
              id="nouveau-role-description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <PermissionGrid
            groupes={inventaire}
            coches={codes}
            onToggle={(code, coche) =>
              setCodes((avant) => {
                const apres = new Set(avant);
                if (coche) apres.add(code);
                else apres.delete(code);
                return apres;
              })
            }
            disabledCodes={disabledCodes}
            raison={raison}
            idPrefixe="nouveau-role"
          />
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              // Garder la saisie après un **refus** est voulu ; la garder après
              // un renoncement rouvrirait la modale sur un rôle abandonné.
              reinitialiser();
              onOpenChange(false);
            }}
          >
            Renoncer
          </Button>
          <Button onClick={creer} disabled={!nom.trim() || !slugValide || creation.isPending}>
            Créer le rôle
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
