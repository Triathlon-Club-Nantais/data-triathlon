"use client";
import { useState } from "react";
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import {
  useAdminPermissions,
  useRoles,
  useDeleteRole,
  useUpdateRole,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import type { PermissionGroup, Role, RoleUpdate, SessionUser } from "@/lib/types";
import { CreateRoleDialog } from "./CreateRoleDialog";
import { PermissionGrid } from "./PermissionGrid";

/**
 * Ce qu'un refus doit dire, et qu'une liste vide ne doit pas dire.
 *
 * Troisième exemplaire assumé, après `PendingProvidersTable` et
 * `AllowedEmailsTable` : les trois ne partagent que la structure 401/403/autre,
 * et c'est leur contenu qui compte. Une fabrique prendrait trois chaînes en
 * argument pour en produire trois.
 *
 * Sur un 403, `data` est `undefined`. Ici l'écran conclurait « aucun rôle
 * n'existe » d'un simple manque de droit — la lecture la plus alarmante
 * possible, sur l'écran qui gouverne tous les autres.
 */
function messageDErreur(erreur: Error): { title: string; description: string } {
  const statut = erreur instanceof ApiError ? erreur.status : 0;
  if (statut === 401) {
    return {
      title: "Session expirée",
      description: "Reconnectez-vous pour consulter les rôles.",
    };
  }
  if (statut === 403) {
    return {
      title: "Accès refusé",
      description:
        "Votre rôle ne permet pas de consulter la composition des rôles. " +
        "Demandez le pouvoir correspondant à un administrateur.",
    };
  }
  return {
    title: "Rôles indisponibles",
    description: "Les rôles n'ont pas pu être chargés. Réessayez plus tard.",
  };
}

function porteurs(nombre: number): string {
  return `${nombre} porteur${nombre > 1 ? "s" : ""}`;
}

function memesCodes(gauche: ReadonlySet<string>, droite: readonly string[]): boolean {
  return gauche.size === droite.length && droite.every((code) => gauche.has(code));
}

const RAISON_NON_PORTE =
  "Vous ne portez pas ce pouvoir : vous ne pouvez ni l'accorder ni le retirer.";

/**
 * Les codes de l'inventaire que la session ne porte pas.
 *
 * La non-amplification est **symétrique** côté serveur : ce qu'on ne porte pas,
 * on ne peut ni l'accorder ni le retirer. Les codes périmés n'y entrent jamais —
 * ils sont hors inventaire, donc hors du calcul, et restent purgeables par tous.
 *
 * Calculé une fois pour l'écran : il ne dépend ni du rôle ouvert ni du panneau,
 * et il vaut pour la grille d'édition **comme** pour celle de la création.
 */
function codesNonPortes(inventaire: PermissionGroup[], portes: readonly string[]): Set<string> {
  const detenus = new Set(portes);
  return new Set(
    inventaire.flatMap((groupe) =>
      groupe.permissions.map((pouvoir) => pouvoir.code).filter((code) => !detenus.has(code)),
    ),
  );
}

/**
 * Ce qui, dans un rôle, se compare pour savoir s'il a bougé sous le brouillon.
 *
 * `holders` en est exclu : il change quand on attribue le rôle ailleurs, ce qui
 * n'entre en conflit avec aucune saisie. Les tableaux sont triés — le serveur ne
 * promet pas leur ordre.
 */
function signature(role: Role): string {
  return JSON.stringify([
    role.name,
    role.description,
    role.is_superuser,
    [...role.permissions].sort(),
    [...role.stale_permissions].sort(),
  ]);
}

/**
 * L'utilisateur connecté franchit-il tout ?
 *
 * **Déduit, pas inféré.** `GET /auth/me` ne rend pas `is_superuser` ; on croise
 * donc les rôles portés avec la liste déjà chargée, ce qui est exactement la
 * définition de `authorization._is_superuser`. Répondre « il porte les dix-huit
 * codes » serait faux : un rôle ordinaire cochant toutes les cases produit la
 * même liste sans franchir les pouvoirs à venir, et la bascule qu'on lui aurait
 * offerte reviendrait en 403.
 */
function estSuperutilisateur(session: SessionUser | null | undefined, roles: Role[]): boolean {
  if (!session) return false;
  return session.roles.some(
    (porte) => roles.find((role) => role.id === porte.id)?.is_superuser ?? false,
  );
}

/** Le panneau d'un rôle : ce qu'il porte, ce qu'on peut y changer, et pourquoi pas le reste. */
function PanneauRole({
  role,
  inventaire,
  figes,
  peutEcrire,
  peutPoserLeStatut,
}: {
  role: Role;
  inventaire: PermissionGroup[];
  figes: ReadonlySet<string>;
  peutEcrire: boolean;
  peutPoserLeStatut: boolean;
}) {
  // Le brouillon naît à l'ouverture du panneau et meurt à sa fermeture :
  // l'accordéon démonte les panneaux fermés (`keepMounted` vaut `false`).
  //
  // `base` est l'état serveur sur lequel il a été ouvert, et **c'est lui**, pas
  // la prop, que tout le panneau compare et affiche. La prop, elle, continue de
  // vivre : `roles` se rafraîchit sous un panneau resté ouvert — une
  // création depuis la même page suffit à l'invalider. Comparer à une prop qui
  // bouge ferait apparaître des modifications que personne n'a faites ; s'y fier
  // pour l'envoi renverrait l'ensemble figé à l'ouverture, effaçant ce qu'un
  // autre administrateur vient d'ajouter.
  const [base, setBase] = useState(role);
  const [nom, setNom] = useState(role.name);
  const [description, setDescription] = useState(role.description);
  const [codes, setCodes] = useState<ReadonlySet<string>>(new Set(role.permissions));
  const [purgeDemandee, setPurgeDemandee] = useState(false);

  const recomposition = useUpdateRole();
  const suppression = useDeleteRole();
  const confirmerLeDanger = useDangerConfirm();

  const nomNet = nom.trim();
  const compositionModifiee = purgeDemandee || !memesCodes(codes, base.permissions);
  const modifie = compositionModifiee || nomNet !== base.name || description !== base.description;
  const purgeAnnoncee = compositionModifiee && base.stale_permissions.length > 0;
  // Le serveur n'offre ni ETag ni `If-Match` : ce rapprochement est le seul
  // endroit où une écriture concurrente peut se voir.
  const conflit = signature(role) !== signature(base);

  function retomberSur(dernier: Role) {
    setBase(dernier);
    setNom(dernier.name);
    setDescription(dernier.description);
    setCodes(new Set(dernier.permissions));
    setPurgeDemandee(false);
  }

  async function appliquer(champs: RoleUpdate, succes: string) {
    try {
      const apres = await recomposition.mutateAsync({ id: role.id, champs });
      retomberSur(apres);
      toast.success(succes);
    } catch (e) {
      // Les `DomainError` sont écrites en français pour être lues telles
      // quelles ; en réécrire une seconde version ferait diverger les deux.
      toast.error((e as Error).message);
      retomberSur(base);
    }
  }

  async function enregistrer() {
    // **Seuls les champs modifiés partent.** `permissions` remplace l'ensemble :
    // l'envoyer sur un simple renommage purgerait les codes périmés en silence.
    const champs: RoleUpdate = {};
    if (nomNet !== base.name) champs.name = nomNet;
    if (description !== base.description) champs.description = description;
    if (compositionModifiee) champs.permissions = [...codes];
    await appliquer(champs, "Rôle enregistré.");
  }

  async function basculerLeStatut() {
    const pose = !base.is_superuser;
    // Confirmé dans les deux sens, mais **neutre** de couleur : ni poser ni
    // retirer le statut ne ferme un accès ni ne détruit une donnée (#499). Le
    // lot n'invente pas une troisième catégorie de gravité pour ce bouton.
    if (
      !(await confirmerLeDanger({
        titre: pose
          ? `Faire de « ${base.name} » un superutilisateur ?`
          : `Retirer le statut de superutilisateur à « ${base.name} » ?`,
        description: pose
          ? "Il franchira tout pouvoir, y compris ceux livrés après lui."
          : "Il ne franchira plus que les pouvoirs qu'il porte explicitement.",
        libelleAction: pose ? "Poser le statut" : "Retirer le statut",
        actionNeutre: true,
      }))
    ) {
      return;
    }
    await appliquer({ is_superuser: pose }, pose ? "Statut posé." : "Statut retiré.");
  }

  async function supprimer() {
    if (
      !(await confirmerLeDanger({
        titre: `Supprimer le rôle « ${role.name} » ?`,
        description: "Ce geste est sans retour.",
      }))
    ) {
      return;
    }
    try {
      await suppression.mutateAsync(role.id);
      toast.success("Rôle supprimé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const raisonDeNonSuppression = role.is_system
    ? "Rôle livré avec l'application."
    : role.holders > 0
      ? `Porté par ${porteurs(role.holders)}. Retirez-le d'abord.`
      : null;

  return (
    <div className="space-y-6 pb-6">
      {conflit && (
        <div role="alert" className="space-y-2 rounded-lg border border-destructive/50 p-4">
          <p className="text-sm font-medium text-destructive">
            Ce rôle a été modifié ailleurs pendant votre édition. Enregistrer maintenant
            écraserait cette modification.
          </p>
          <Button size="sm" variant="outline" onClick={() => retomberSur(role)}>
            Repartir de la version à jour
          </Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`role-${role.id}-nom`}>Nom du rôle</Label>
          <Input
            id={`role-${role.id}-nom`}
            value={nom}
            disabled={!peutEcrire}
            onChange={(e) => setNom(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`role-${role.id}-description`}>Description</Label>
          <Textarea
            id={`role-${role.id}-description`}
            rows={2}
            value={description}
            disabled={!peutEcrire}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
      </div>

      {base.is_superuser && (
        <Card className="gap-1 border-primary/40 bg-primary/5 p-4">
          <p className="text-sm font-semibold">Superutilisateur</p>
          <p className="text-sm text-[var(--tcn-text-faint)]">
            Ce rôle franchit tout pouvoir, y compris ceux livrés après lui. Sa composition
            ci-dessous reste enregistrée, mais elle ne décide de rien tant que ce statut est
            posé.
          </p>
        </Card>
      )}

      <PermissionGrid
        groupes={inventaire}
        coches={codes}
        // Un rôle superutilisateur ne se compose pas à la case : sa grille reste
        // affichée, inerte, et la phrase ci-dessus dit pourquoi.
        onToggle={
          base.is_superuser || !peutEcrire
            ? undefined
            : (code, coche) =>
                setCodes((avant) => {
                  const apres = new Set(avant);
                  if (coche) apres.add(code);
                  else apres.delete(code);
                  return apres;
                })
        }
        disabledCodes={figes}
        raison={RAISON_NON_PORTE}
        idPrefixe={`role-${role.id}`}
      />

      {base.stale_permissions.length > 0 && (
        <fieldset className="space-y-2 rounded-lg border border-dashed p-4">
          <legend className="px-1 text-sm font-semibold">Codes périmés</legend>
          <p className="text-sm text-[var(--tcn-text-faint)]">
            Ce rôle porte des codes que l&apos;application ne connaît plus. Ils sont{" "}
            <strong>sans effet</strong> et n&apos;accordent rien.
          </p>
          <ul className="space-y-1">
            {base.stale_permissions.map((code) => (
              <li key={code} className="font-mono text-sm">
                {code}
              </li>
            ))}
          </ul>
          {peutEcrire && (
            // Il n'existe aucune ressource pour les retirer seuls : leur purge
            // est l'effet d'un `PATCH` de la composition. Ce bouton ne fait donc
            // que marquer la composition comme à réécrire — et se rétracte.
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPurgeDemandee(!purgeDemandee)}
            >
              {purgeDemandee ? "Annuler la purge" : "Purger ces codes"}
            </Button>
          )}
        </fieldset>
      )}

      {purgeAnnoncee && (
        <p className="text-sm font-medium text-destructive">
          En enregistrant, ces codes périmés disparaîtront :{" "}
          {base.stale_permissions.join(", ")}.
        </p>
      )}

      {peutEcrire && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            onClick={enregistrer}
            disabled={!modifie || !nomNet || conflit || recomposition.isPending}
          >
            Enregistrer
          </Button>

          {peutPoserLeStatut && (
            <>
              <Button
                variant="outline"
                onClick={basculerLeStatut}
                disabled={modifie || conflit || recomposition.isPending}
              >
                {base.is_superuser
                  ? "Retirer le statut de superutilisateur"
                  : "Faire de ce rôle un superutilisateur"}
              </Button>
              {/* La bascule n'envoie que `is_superuser`, et la réponse rend
                  l'état d'avant : l'appliquer par-dessus un brouillon le
                  jetterait en annonçant un succès. */}
              {modifie && (
                <span className="text-sm text-[var(--tcn-text-faint)]">
                  Enregistrez vos modifications avant de changer le statut.
                </span>
              )}
            </>
          )}

          <div className="ms-auto flex items-center gap-2">
            {raisonDeNonSuppression && (
              <span className="text-sm text-[var(--tcn-text-faint)]">{raisonDeNonSuppression}</span>
            )}
            <Button
              variant="destructive"
              onClick={supprimer}
              disabled={raisonDeNonSuppression !== null || suppression.isPending}
            >
              Supprimer
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Écran de composition des droits d'un rôle (#240).
 *
 * Un accordéon plutôt qu'un maître-détail ou une modale : un seul rôle ouvert à
 * la fois, donc une seule grille de dix-huit cases à l'écran, et rien à écrire
 * pour que cela tienne sur un téléphone. Les panneaux fermés étant démontés,
 * c'est aussi lui qui donne au brouillon sa durée de vie.
 */
export function RolePermissionsEditor() {
  const inventaire = useAdminPermissions();
  const roles = useRoles();
  const session = useSession();
  const [creationOuverte, setCreationOuverte] = useState(false);

  // La session compte parmi les lectures dont l'écran dépend : `useSession` ne
  // réessaie pas, donc une panne sur `/auth/me` laisse ses données à `undefined`
  // pour de bon. En déduire « cette personne ne porte aucun pouvoir » figerait
  // toutes les cases en affirmant une chose fausse, y compris à un
  // superutilisateur — droits **inconnus** n'est pas droits **nuls**.
  const erreur = roles.error ?? inventaire.error ?? session.error;
  if (erreur) return <EmptyState {...messageDErreur(erreur)} />;
  if (!roles.data || !inventaire.data || session.isPending) {
    return <Skeleton className="h-64 w-full" />;
  }

  const compte = session.data;
  // `roles:read` et `roles:write` sont deux pouvoirs distincts, attribuables
  // séparément : les lectures de cet écran exigent le premier, toutes ses
  // écritures le second. Le rail de navigation filtre déjà sur `roles:write`,
  // mais l'URL reste atteignable.
  const peutEcrire = compte?.permissions.includes("roles:write") ?? false;
  const peutPoserLeStatut = peutEcrire && estSuperutilisateur(compte, roles.data);
  const figes = codesNonPortes(inventaire.data, compte?.permissions ?? []);

  return (
    <div className="space-y-4">
      {peutEcrire ? (
        <div className="flex justify-end">
          <Button onClick={() => setCreationOuverte(true)}>Créer un rôle</Button>
        </div>
      ) : (
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Cet écran est en consultation : recomposer un rôle demande le pouvoir « Composer les
          rôles ».
        </p>
      )}

      {peutEcrire && (
        <CreateRoleDialog
          inventaire={inventaire.data}
          disabledCodes={figes}
          raison={RAISON_NON_PORTE}
          open={creationOuverte}
          onOpenChange={setCreationOuverte}
        />
      )}

      <Accordion className="rounded-xl border px-4">
        {roles.data.map((role) => (
          <AccordionItem key={role.id} value={String(role.id)}>
            <AccordionTrigger className="cursor-pointer hover:no-underline">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold group-hover/accordion-trigger:underline">
                  {role.name}
                </span>
                {role.is_system && <Badge variant="outline">livré</Badge>}
                {role.is_superuser && <Badge>superutilisateur</Badge>}
                <span className="text-[var(--tcn-text-faint)]">{porteurs(role.holders)}</span>
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <PanneauRole
                role={role}
                inventaire={inventaire.data}
                figes={figes}
                peutEcrire={peutEcrire}
                peutPoserLeStatut={peutPoserLeStatut}
              />
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
