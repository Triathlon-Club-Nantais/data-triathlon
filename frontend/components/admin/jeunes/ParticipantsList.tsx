"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAddEntrainementParticipant,
  useEntrainement,
  useRemoveEntrainementParticipant,
} from "@/lib/queries/admin";

/**
 * La liste des participants inscrits à un entraînement (#868).
 *
 * **`jeune_id` seul, saisi à la main** : le profil du jeune référencé (#867)
 * n'existe pas encore côté modèle — cette ressource ne connaît que
 * l'identifiant, pas le nom. Un sélecteur par nom rouvrira ce composant une
 * fois #867 mergée, sans changer son contrat.
 */
export function ParticipantsList({
  entrainementId,
  peutEcrire,
}: {
  entrainementId: number;
  peutEcrire: boolean;
}) {
  const detail = useEntrainement(entrainementId);
  const inscrire = useAddEntrainementParticipant();
  const desinscrire = useRemoveEntrainementParticipant();
  const [jeuneId, setJeuneId] = useState("");

  const participants = detail.data?.participants ?? [];

  async function onSubmit(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    const id = Number(jeuneId);
    if (!Number.isInteger(id) || id <= 0) return;
    try {
      await inscrire.mutateAsync({ entrainementId, jeuneId: id });
      setJeuneId("");
      toast.success("Jeune inscrit.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function retirer(jeune_id: number) {
    // Sans confirmation, délibérément : désinscrire quelqu'un d'un
    // entraînement ne détruit rien — le geste se refait d'un clic, même
    // raisonnement que le retrait d'un membre de groupe (#197).
    try {
      await desinscrire.mutateAsync({ entrainementId, jeuneId: jeune_id });
      toast.success("Jeune désinscrit.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-3">
      {peutEcrire && (
        <form onSubmit={onSubmit} className="flex items-end gap-2">
          <div className="space-y-1.5">
            <Label htmlFor="participant-jeune-id">Identifiant du jeune</Label>
            <Input
              id="participant-jeune-id"
              type="number"
              min={1}
              className="w-32"
              value={jeuneId}
              onChange={(e) => setJeuneId(e.target.value)}
            />
          </div>
          <Button type="submit" size="sm" disabled={inscrire.isPending || !jeuneId}>
            Inscrire
          </Button>
        </form>
      )}

      {detail.isLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : detail.error ? (
        <p className="text-destructive text-sm">
          La liste des participants n&apos;a pas pu être chargée. Réessayez plus tard.
        </p>
      ) : participants.length === 0 ? (
        <p className="text-[var(--tcn-text-faint)] text-sm">Aucun participant inscrit.</p>
      ) : (
        <ul className="divide-border divide-y">
          {participants.map((participant) => (
            <li
              key={participant.jeune_id}
              className="flex items-center justify-between gap-2 py-2"
            >
              <span>Jeune n° {participant.jeune_id}</span>
              {peutEcrire && (
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Désinscrire le jeune n° ${participant.jeune_id}`}
                  onClick={() => retirer(participant.jeune_id)}
                >
                  Désinscrire
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
