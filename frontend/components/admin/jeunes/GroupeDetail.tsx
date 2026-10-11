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
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import {
  useAddTrainingGroupMember,
  useDeleteTrainingGroup,
  useProfiles,
  useRemoveTrainingGroupMember,
  useRenameTrainingGroup,
  useTrainingGroup,
} from "@/lib/queries/admin";
import { localToday } from "@/lib/utils/date";

/**
 * Un groupe : son nom, ses membres, et les gestes de `jeunes:write` (#1291).
 * Ajouter ou retirer un membre resynchronise les séances à venir côté serveur.
 */
export function GroupeDetail({
  groupId,
  peutEcrire,
  onOpenChange,
}: {
  groupId: number;
  peutEcrire: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const { data, isPending, error } = useTrainingGroup(groupId);
  const profils = useProfiles();
  const renommer = useRenameTrainingGroup();
  const supprimer = useDeleteTrainingGroup();
  const ajouter = useAddTrainingGroupMember();
  const retirer = useRemoveTrainingGroupMember();
  const confirmer = useDangerConfirm();

  const membres = data?.members ?? [];
  const idsMembres = new Set(membres.map((membre) => membre.id));
  const ajoutables = (profils.data ?? []).filter((profil) => !idsMembres.has(profil.id));
  const aujourdhui = localToday();

  async function agir(geste: () => Promise<unknown>, succes: string) {
    try {
      await geste();
      toast.success(succes);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function detruire() {
    if (!data) return;
    const accord = await confirmer({
      titre: `Supprimer le groupe « ${data.name} » ?`,
      description:
        "Ses membres restent inscrits aux séances existantes, mais les prochaines séances ne les inscriront plus d'office. Ce geste est définitif.",
      libelleAction: "Supprimer le groupe",
    });
    if (!accord) return;
    try {
      await supprimer.mutateAsync(groupId);
      toast.success("Groupe supprimé.");
      onOpenChange(false);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{data?.name ?? "Groupe"}</DialogTitle>
          <DialogDescription>
            Les membres de ce groupe sont inscrits d&apos;office aux séances à venir qui le
            visent, tant que l&apos;appel n&apos;a pas commencé.
          </DialogDescription>
        </DialogHeader>

        {isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : error || !data ? (
          <p className="text-destructive text-sm">
            Ce groupe n&apos;a pas pu être chargé. Réessayez plus tard.
          </p>
        ) : (
          <div className="space-y-4">
            {peutEcrire && (
              <Renommer
                key={data.name}
                nomActuel={data.name}
                enCours={renommer.isPending}
                renommer={(nom) =>
                  agir(() => renommer.mutateAsync({ id: groupId, name: nom }), "Groupe renommé.")
                }
              />
            )}

            {peutEcrire && (
              <div className="space-y-1.5">
                <Label htmlFor="groupe-ajouter">Ajouter un jeune</Label>
                <select
                  id="groupe-ajouter"
                  className="border-input h-9 min-h-11 w-full rounded-md border bg-transparent px-2 text-sm md:min-h-0"
                  value=""
                  disabled={ajouter.isPending || ajoutables.length === 0}
                  onChange={(e) =>
                    e.target.value &&
                    agir(
                      () => ajouter.mutateAsync({ groupId, profileId: Number(e.target.value) }),
                      "Jeune ajouté au groupe.",
                    )
                  }
                >
                  <option value="" disabled>
                    Choisir un jeune…
                  </option>
                  {ajoutables.map((profil) => (
                    <option key={profil.id} value={profil.id}>
                      {profil.first_name} {profil.last_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {membres.length === 0 ? (
              <p className="text-[var(--tcn-text-faint)] text-sm">Aucun membre pour l&apos;instant.</p>
            ) : (
              <ul className="divide-border divide-y">
                {membres.map((membre) => {
                  const nomMembre = `${membre.first_name} ${membre.last_name}`;
                  const adhesionTerminee =
                    membre.membership_ended_on !== null && membre.membership_ended_on < aujourdhui;
                  return (
                    <li key={membre.id} className="flex items-center justify-between gap-2 py-2">
                      <span className="flex min-w-0 flex-wrap items-center gap-2">
                        <span>{nomMembre}</span>
                        {membre.category && <Badge variant="secondary">{membre.category}</Badge>}
                        {adhesionTerminee && (
                          <Badge variant="outline">Adhésion terminée, plus inscrit d&apos;office</Badge>
                        )}
                      </span>
                      {peutEcrire && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="tcn-cible-tactile"
                          aria-label={`Retirer ${nomMembre}`}
                          onClick={() =>
                            agir(
                              () => retirer.mutateAsync({ groupId, profileId: membre.id }),
                              "Jeune retiré du groupe.",
                            )
                          }
                        >
                          Retirer
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}

            {peutEcrire && (
              <Button variant="destructive" className="w-fit" disabled={supprimer.isPending} onClick={detruire}>
                Supprimer le groupe
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Remonté à chaque nom serveur (`key`), il repart du nom à jour sans effet de synchronisation. */
function Renommer({
  nomActuel,
  enCours,
  renommer,
}: {
  nomActuel: string;
  enCours: boolean;
  renommer: (nom: string) => void;
}) {
  const [nom, setNom] = useState(nomActuel);
  return (
    <form
      className="flex items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (nom.trim()) renommer(nom.trim());
      }}
    >
      <div className="min-w-0 flex-1 space-y-1.5">
        <Label htmlFor="groupe-renommer">Nom</Label>
        <Input id="groupe-renommer" required value={nom} onChange={(e) => setNom(e.target.value)} />
      </div>
      <Button type="submit" variant="outline" disabled={enCours}>
        Renommer
      </Button>
    </form>
  );
}
