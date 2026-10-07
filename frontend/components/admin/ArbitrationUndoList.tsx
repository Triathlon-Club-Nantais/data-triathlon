"use client";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  useConfirmedIdentityClubs,
  useIgnoredCourseDuplicates,
  useIgnoredIdentityPairs,
  useUnconfirmIdentityClub,
  useUnignoreCourseDuplicate,
  useUnignoreIdentityPair,
} from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";

export interface UndoItem {
  id: number;
  label: ReactNode;
  /** Nomme la ligne pour le lecteur d'écran : plusieurs « Annuler » se suivent. */
  undoLabel: string;
  date?: string;
}

/**
 * Les arbitrages déjà rendus, à revoir et annuler (#1243). Repliée par défaut
 * sur un `<details>` natif : la file à traiter reste le sujet de l'écran.
 */
export function UndoList({
  title,
  items,
  empty,
  pending,
  onUndo,
}: {
  title: string;
  items: UndoItem[];
  empty: string;
  pending: boolean;
  onUndo: (id: number) => void;
}) {
  return (
    <details className="text-sm">
      <summary className="tcn-lien-action cursor-pointer font-medium">{`${title} (${items.length})`}</summary>
      {items.length === 0 ? (
        <p className="mt-2 text-[var(--tcn-text-faint)]">{empty}</p>
      ) : (
        <ul className="mt-2 divide-y">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                {item.label}
                {item.date && (
                  <span className="ml-2 text-[var(--tcn-text-faint)]">{`le ${formatDate(item.date)}`}</span>
                )}
              </span>
              <Button
                variant="outline"
                size="sm"
                aria-label={item.undoLabel}
                disabled={pending}
                onClick={() => onUndo(item.id)}
              >
                Annuler
              </Button>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

function notifier(message: string) {
  return {
    onSuccess: () => toast.success(message),
    onError: (erreur: Error) => toast.error(erreur.message),
  };
}

function nomme(personne: { nom: string; prenom: string }): string {
  return `${personne.nom} ${personne.prenom}`;
}

/** Paires écartées et clubs confirmés de la revue d'identité. */
export function IdentityArbitrations() {
  const paires = useIgnoredIdentityPairs();
  const clubs = useConfirmedIdentityClubs();
  const rouvrirPaire = useUnignoreIdentityPair();
  const rouvrirClub = useUnconfirmIdentityClub();
  if (!paires.data || !clubs.data) return null;

  return (
    <div className="space-y-3">
      <UndoList
        title="Paires écartées"
        empty="Aucune paire écartée."
        pending={rouvrirPaire.isPending}
        items={paires.data.pairs.map((paire) => {
          const noms = paire.athletes.map(nomme).join(" et ");
          return {
            id: paire.id,
            label: noms,
            undoLabel: `Annuler la mise à l'écart de ${noms}`,
            date: paire.ignored_at,
          };
        })}
        onUndo={(id) => rouvrirPaire.mutate(id, notifier("La paire revient dans la revue."))}
      />
      <UndoList
        title="Clubs confirmés"
        empty="Aucun club confirmé."
        pending={rouvrirClub.isPending}
        items={clubs.data.clubs.map((club) => ({
          id: club.id,
          label: `${nomme(club)} : ${club.club_key}`,
          undoLabel: `Annuler la confirmation de ${club.club_key} pour ${nomme(club)}`,
          date: club.confirmed_at,
        }))}
        onUndo={(id) => rouvrirClub.mutate(id, notifier("La fiche sera de nouveau signalée pour ce club."))}
      />
    </div>
  );
}

/** Paires d'épreuves écartées de la liste des doublons suspects. */
export function IgnoredCourseDuplicates() {
  const { data } = useIgnoredCourseDuplicates();
  const rouvrir = useUnignoreCourseDuplicate();
  if (!data) return null;

  return (
    <UndoList
      title="Paires écartées"
      empty="Aucune paire écartée."
      pending={rouvrir.isPending}
      items={data.pairs.map((paire) => {
        const noms = paire.courses.map((c) => `${c.name} (n° ${c.id})`).join(" et ");
        return {
          id: paire.id,
          label: noms,
          undoLabel: `Annuler la mise à l'écart de ${noms}`,
          date: paire.ignored_at,
        };
      })}
      onUndo={(id) => rouvrir.mutate(id, notifier("La paire revient dans la liste des doublons suspects."))}
    />
  );
}
