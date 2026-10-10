"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { EntrainementDetailDialog } from "@/components/admin/jeunes/EntrainementDetailDialog";
import { EntrainementForm } from "@/components/admin/jeunes/EntrainementForm";
import { useCreateTrainingSession, useTrainingSessions } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { cn } from "@/lib/utils";
import { formatDate, localToday } from "@/lib/utils/date";
import type { TrainingSession } from "@/lib/types";

const REFUS = { sujet: "entraînements", action: "consulter le calendrier des entraînements" };

/**
 * Le calendrier des entraînements jeunes (#868) — une liste de cartes plutôt
 * qu'un tableau : c'est l'écran le plus susceptible d'être ouvert depuis un
 * téléphone, au bord d'un bassin ou d'un plateau d'entraînement.
 */
export function CalendrierEntrainements() {
  const { data, isLoading, error } = useTrainingSessions();
  const session = useSession();
  const creer = useCreateTrainingSession();
  const [ouvert, setOuvert] = useState<TrainingSession | null>(null);

  // Confort d'affichage seul : chaque ressource porte sa garde côté API.
  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;

  async function creerEntrainement(champs: {
    date: string;
    start_time: string | null;
    location: string | null;
    session_type: string | null;
  }) {
    try {
      await creer.mutateAsync(champs);
      toast.success("Entraînement créé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  // Le backend trie par date croissante : l'encadrant cherche d'abord la
  // prochaine séance, les passées viennent ensuite, la plus récente en tête.
  const aujourdhui = localToday();
  const aVenir = (data ?? []).filter((entrainement) => entrainement.date >= aujourdhui);
  const passees = (data ?? []).filter((entrainement) => entrainement.date < aujourdhui).reverse();

  function carte(entrainement: TrainingSession) {
    const duJour = entrainement.date === aujourdhui;
    return (
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
        className={cn(
          "cursor-pointer space-y-2 p-4",
          duJour && "ring-2 ring-[var(--tcn-orange)]",
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <span className="font-medium">{formatDate(entrainement.date)}</span>
            {duJour && <Badge>Aujourd&apos;hui</Badge>}
          </span>
          {entrainement.start_time && (
            <span className="text-[var(--tcn-text-faint)] text-sm">
              {entrainement.start_time.slice(0, 5)}
            </span>
          )}
        </div>
        <div className="text-[var(--tcn-text-faint)] text-sm">
          {entrainement.location || "Lieu non renseigné"}
        </div>
        <div className="flex items-center justify-between gap-2">
          {entrainement.session_type ? (
            <Badge variant="secondary">{entrainement.session_type}</Badge>
          ) : (
            <span />
          )}
          <span className="text-[var(--tcn-text-faint)] text-xs">
            {entrainement.participant_count} inscrit
            {entrainement.participant_count > 1 ? "s" : ""}
          </span>
        </div>
      </Card>
    );
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
        <div className="space-y-8">
          <section aria-labelledby="seances-a-venir" className="space-y-3">
            <h2 id="seances-a-venir" className="font-heading text-lg font-semibold">
              Séances à venir
            </h2>
            {aVenir.length === 0 ? (
              <p className="text-[var(--tcn-text-faint)] text-sm">Aucune séance à venir.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {aVenir.map(carte)}
              </div>
            )}
          </section>
          {passees.length > 0 && (
            <section aria-labelledby="seances-passees" className="space-y-3">
              <h2 id="seances-passees" className="font-heading text-lg font-semibold">
                Séances passées
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {passees.map(carte)}
              </div>
            </section>
          )}
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
