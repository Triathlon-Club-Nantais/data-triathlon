"use client";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAddEntrainementParticipant,
  useEntrainement,
  useProfiles,
  useRemoveEntrainementParticipant,
} from "@/lib/queries/admin";

/**
 * La liste des participants inscrits à un entraînement (#868).
 *
 * Inscription par nom, depuis la liste des profils (#867) : même `<select>`
 * natif que l'ajout d'un jeune dans `AppelPresence`. Le contrat de la
 * ressource reste l'identifiant, seul l'écran résout le nom.
 */
export function ParticipantsList({
  entrainementId,
  peutEcrire,
}: {
  entrainementId: number;
  peutEcrire: boolean;
}) {
  const detail = useEntrainement(entrainementId);
  const profils = useProfiles();
  const inscrire = useAddEntrainementParticipant();
  const desinscrire = useRemoveEntrainementParticipant();

  const participants = detail.data?.participants ?? [];
  const profilsParId = new Map((profils.data ?? []).map((profil) => [profil.id, profil]));
  const idsInscrits = new Set(participants.map((participant) => participant.jeune_id));
  const inscriptibles = (profils.data ?? []).filter((profil) => !idsInscrits.has(profil.id));

  function nomDe(jeuneId: number): string {
    const profil = profilsParId.get(jeuneId);
    return profil ? `${profil.first_name} ${profil.last_name}` : `Jeune n° ${jeuneId}`;
  }

  async function inscrireJeune(jeuneId: number) {
    try {
      await inscrire.mutateAsync({ entrainementId, jeuneId });
      toast.success("Jeune inscrit.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function retirer(jeune_id: number) {
    // Sans confirmation, délibérément : désinscrire quelqu'un d'un
    // entraînement ne détruit rien, le geste se refait d'un clic (même
    // raisonnement que le retrait d'un membre de groupe, #197).
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
        <div className="space-y-1.5">
          <Label htmlFor="participant-jeune">Inscrire un jeune</Label>
          <select
            id="participant-jeune"
            className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm"
            value=""
            disabled={inscrire.isPending || inscriptibles.length === 0}
            onChange={(e) => e.target.value && inscrireJeune(Number(e.target.value))}
          >
            <option value="" disabled>
              Choisir un jeune…
            </option>
            {inscriptibles.map((profil) => (
              <option key={profil.id} value={profil.id}>
                {profil.first_name} {profil.last_name}
              </option>
            ))}
          </select>
          {profils.error && (
            <p className="text-[var(--tcn-text-faint)] text-xs">
              La liste des jeunes n&apos;a pas pu être chargée : inscrire un
              jeune n&apos;est pas possible pour l&apos;instant.
            </p>
          )}
        </div>
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
          {participants.map((participant) => {
            const nom = nomDe(participant.jeune_id);
            return (
              <li
                key={participant.jeune_id}
                className="flex items-center justify-between gap-2 py-2"
              >
                <span>{nom}</span>
                {peutEcrire && (
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Désinscrire ${nom}`}
                    onClick={() => retirer(participant.jeune_id)}
                  >
                    Désinscrire
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
