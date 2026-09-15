"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useAddProfileLogEntry, useProfile, useUpdateProfile } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import { calculerAge } from "@/lib/utils/age";

const REFUS = { sujet: "jeunes", action: "consulter ce profil" };

/**
 * Détail d'un profil individuel (#867, epic #863) — informations
 * personnelles, journal de bord, et les deux formulaires d'édition, gardés
 * côté client par `jeunes:write` (patron #496, garde de confort seulement :
 * chaque écriture porte sa propre garde côté API).
 */
export function ProfileDetail({ profileId }: { profileId: number }) {
  const { data, isLoading, error } = useProfile(profileId);
  const session = useSession();
  const modifier = useUpdateProfile();
  const ajouterEntree = useAddProfileLogEntry();
  const [edition, setEdition] = useState(false);
  const [contact, setContact] = useState("");
  const [notes, setNotes] = useState("");
  const [nouvelleEntree, setNouvelleEntree] = useState("");

  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;

  function ouvrirEdition() {
    setContact(data?.emergency_contact ?? "");
    setNotes(data?.notes ?? "");
    setEdition(true);
  }

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    try {
      await modifier.mutateAsync({
        id: profileId,
        champs: { emergency_contact: contact, notes },
      });
      setEdition(false);
      toast.success("Profil mis à jour.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function ajouter(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!nouvelleEntree.trim()) return;
    try {
      await ajouterEntree.mutateAsync({ id: profileId, text: nouvelleEntree.trim() });
      setNouvelleEntree("");
      toast.success("Entrée ajoutée au journal.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error) return <EmptyState {...messageDeRefus(error, REFUS)} />;
  if (!data) return null;

  const age = calculerAge(data.birth_date);

  return (
    <div className="space-y-6">
      <Card className="space-y-3 p-4">
        <div className="text-lg font-bold">
          {data.first_name} {data.last_name}
        </div>
        <div className="text-[var(--tcn-text-faint)] text-sm">
          {age === null ? "Âge inconnu" : `${age} ans`}
        </div>

        {edition ? (
          <form onSubmit={enregistrer} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="jeune-contact">Contact d&apos;urgence</Label>
              <Input
                id="jeune-contact"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="jeune-notes">Notes</Label>
              <Textarea
                id="jeune-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={modifier.isPending}>
                Enregistrer
              </Button>
              <Button type="button" variant="outline" onClick={() => setEdition(false)}>
                Annuler
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div>
              <span className="font-medium">Contact d&apos;urgence : </span>
              {data.emergency_contact || "—"}
            </div>
            <div>
              <span className="font-medium">Notes : </span>
              {data.notes || "—"}
            </div>
            {peutEcrire && (
              <Button size="sm" variant="outline" onClick={ouvrirEdition}>
                Modifier le profil
              </Button>
            )}
          </>
        )}
      </Card>

      <Card className="space-y-3 p-4">
        <div className="text-lg font-bold">Journal de bord</div>

        {peutEcrire && (
          <form onSubmit={ajouter} className="space-y-2">
            <Label htmlFor="jeune-nouvelle-entree">Nouvelle entrée</Label>
            <Textarea
              id="jeune-nouvelle-entree"
              value={nouvelleEntree}
              onChange={(e) => setNouvelleEntree(e.target.value)}
              placeholder="Ce qui vaut la peine d'être noté après une séance."
            />
            <Button type="submit" size="sm" disabled={ajouterEntree.isPending}>
              Ajouter au journal
            </Button>
          </form>
        )}

        {data.log_entries.length === 0 ? (
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Aucune entrée pour l&apos;instant.
          </p>
        ) : (
          <ul className="space-y-3">
            {data.log_entries.map((entree) => (
              <li key={entree.id} className="border-t pt-3 first:border-t-0 first:pt-0">
                <div className="text-[var(--tcn-text-faint)] text-xs">
                  {formatDate(entree.entry_date)}
                  {entree.created_by_name ? ` — ${entree.created_by_name}` : ""}
                </div>
                <div className="whitespace-pre-wrap text-sm">{entree.text}</div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
