"use client";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { TrainingParticipant, Profile } from "@/lib/types";

/**
 * L'appel de fin (#869, US2) — reboucle sur les jeunes marqués présents à
 * l'appel de début pour vérifier qu'aucun n'est manquant.
 *
 * **Aucune écriture, aucun appel réseau** (FR-007, research.md D2) : la liste
 * de présents vient des `participants` déjà chargés par l'écran parent
 * (`AppelPresence`, via `GET /admin/training-sessions/{id}`), et l'état des
 * cases cochées ne vit que dans ce composant — il n'existe nulle part côté
 * serveur. Remonter ce composant (bascule d'onglet, réouverture de l'écran)
 * réinitialise l'appel de fin, ce qui **est** le comportement voulu.
 */
export function AppelFin({
  participants,
  profils,
}: {
  participants: TrainingParticipant[];
  profils: Profile[];
}) {
  const profilsParId = new Map(profils.map((profil) => [profil.id, profil]));
  const presents = participants.filter((participant) => participant.present === true);
  const [retrouves, setRetrouves] = useState<Set<number>>(new Set());

  function basculer(profileId: number) {
    setRetrouves((precedent) => {
      const suivant = new Set(precedent);
      if (suivant.has(profileId)) {
        suivant.delete(profileId);
      } else {
        suivant.add(profileId);
      }
      return suivant;
    });
  }

  if (presents.length === 0) {
    return (
      <EmptyState
        title="Rien à vérifier"
        description="Aucun jeune n'a encore été pointé présent à l'appel de début."
      />
    );
  }

  // `retrouves` n'est jamais réconcilié avec les props : un id qui a quitté
  // `presents` ne doit pas réduire le compte.
  const manquants = presents.filter((participant) => !retrouves.has(participant.profile_id)).length;

  return (
    <div className="space-y-4">
      <p aria-live="polite" className="text-sm font-medium">
        {manquants === 0
          ? "Tous les jeunes présents à l'appel de début ont été retrouvés."
          : `${manquants} jeune${manquants > 1 ? "s" : ""} restant${manquants > 1 ? "s" : ""} à vérifier.`}
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {presents.map((participant) => {
          const profil = profilsParId.get(participant.profile_id);
          const nom = profil
            ? `${profil.first_name} ${profil.last_name}`
            : `Jeune n° ${participant.profile_id}`;
          const retrouve = retrouves.has(participant.profile_id);
          return (
            <Card key={participant.profile_id} className="p-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={retrouve}
                  onChange={() => basculer(participant.profile_id)}
                  aria-label={nom}
                />
                <span className={retrouve ? "text-[var(--tcn-text-faint)]" : "font-medium"}>
                  {nom}
                </span>
              </label>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
