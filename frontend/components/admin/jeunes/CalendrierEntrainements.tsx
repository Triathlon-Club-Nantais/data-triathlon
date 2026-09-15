"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { EntrainementDetailDialog } from "@/components/admin/jeunes/EntrainementDetailDialog";
import { EntrainementForm } from "@/components/admin/jeunes/EntrainementForm";
import { useCreateEntrainement, useEntrainements } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDate } from "@/lib/utils/date";
import type { Entrainement } from "@/lib/types";

const REFUS = { sujet: "entraînements", action: "consulter le calendrier des entraînements" };

/**
 * Le calendrier des entraînements jeunes (#868) — une liste de cartes plutôt
 * qu'un tableau : c'est l'écran le plus susceptible d'être ouvert depuis un
 * téléphone, au bord d'un bassin ou d'un plateau d'entraînement.
 */
export function CalendrierEntrainements() {
  const { data, isLoading, error } = useEntrainements();
  const session = useSession();
  const creer = useCreateEntrainement();
  const [ouvert, setOuvert] = useState<Entrainement | null>(null);

  // Confort d'affichage seul : chaque ressource porte sa garde côté API.
  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;

  async function creerEntrainement(champs: {
    date: string;
    heure_debut: string | null;
    lieu: string | null;
    type_seance: string | null;
  }) {
    try {
      await creer.mutateAsync(champs);
      toast.success("Entraînement créé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {peutEcrire && (
        <EntrainementForm
          soumettre={creerEntrainement}
          enCours={creer.isPending}
          libelleSoumission="Créer la séance"
        />
      )}

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDeRefus(error, REFUS)} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Aucun entraînement"
          description="Le calendrier est vide pour l'instant. Créez la première séance depuis ce formulaire."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((entrainement) => (
            <Card
              key={entrainement.id}
              role="button"
              tabIndex={0}
              onClick={() => setOuvert(entrainement)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOuvert(entrainement);
                }
              }}
              className="cursor-pointer space-y-2 p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{formatDate(entrainement.date)}</span>
                {entrainement.heure_debut && (
                  <span className="text-[var(--tcn-text-faint)] text-sm">
                    {entrainement.heure_debut.slice(0, 5)}
                  </span>
                )}
              </div>
              <div className="text-[var(--tcn-text-faint)] text-sm">
                {entrainement.lieu || "Lieu non renseigné"}
              </div>
              <div className="flex items-center justify-between gap-2">
                {entrainement.type_seance ? (
                  <Badge variant="secondary">{entrainement.type_seance}</Badge>
                ) : (
                  <span />
                )}
                <span className="text-[var(--tcn-text-faint)] text-xs">
                  {entrainement.participant_count} inscrit
                  {entrainement.participant_count === 1 ? "" : "s"}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {ouvert && (
        <EntrainementDetailDialog
          entrainement={ouvert}
          peutEcrire={peutEcrire}
          open
          onOpenChange={(o) => !o && setOuvert(null)}
        />
      )}
    </div>
  );
}
