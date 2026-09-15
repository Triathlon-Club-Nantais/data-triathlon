"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useCreateProfile, useProfiles } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { calculerAge } from "@/lib/utils/age";

/**
 * Liste des profils individuels (#867, epic #863) — cartes seules, sans
 * double-arbre grille/cartes (#461) : l'usage principal est le téléphone
 * (research.md D3 de la feature), une grille desktop n'a pas de valeur
 * ajoutée sur un écran à quelques champs.
 */
const REFUS = { sujet: "jeunes", action: "consulter les profils" };

export function ProfilesList() {
  const { data, isLoading, error } = useProfiles();
  const session = useSession();
  const creer = useCreateProfile();
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");

  // Confort d'affichage seul : chaque ressource porte sa garde côté API
  // (patron #496 — `GroupsTable`).
  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;

  async function soumettre(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!prenom.trim() || !nom.trim()) return;
    try {
      await creer.mutateAsync({ first_name: prenom.trim(), last_name: nom.trim() });
      setPrenom("");
      setNom("");
      toast.success("Profil créé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {peutEcrire && (
        <form onSubmit={soumettre} className="flex flex-wrap items-end gap-2">
          <div className="space-y-1.5">
            <Label htmlFor="jeune-prenom">Prénom</Label>
            <Input
              id="jeune-prenom"
              className="w-40"
              required
              value={prenom}
              onChange={(e) => setPrenom(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="jeune-nom">Nom</Label>
            <Input
              id="jeune-nom"
              className="w-40"
              required
              value={nom}
              onChange={(e) => setNom(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={creer.isPending}>
            Créer le profil
          </Button>
        </form>
      )}

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDeRefus(error, REFUS)} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Aucun jeune référencé"
          description="Un profil rassemble le contact d'urgence et le journal de bord d'un jeune. Créez-en un pour commencer."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((profil) => {
            const age = calculerAge(profil.birth_date);
            return (
              <Link key={profil.id} href={`/admin/jeunes/${profil.id}`}>
                <Card className="p-4 transition-colors hover:bg-[var(--tcn-orange-08)]">
                  <div className="font-medium">
                    {profil.first_name} {profil.last_name}
                  </div>
                  <div className="text-[var(--tcn-text-faint)] text-sm">
                    {age === null ? "Âge inconnu" : `${age} ans`}
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
