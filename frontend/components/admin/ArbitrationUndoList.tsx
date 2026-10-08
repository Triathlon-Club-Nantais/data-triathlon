"use client";
import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { messageDeRefus } from "@/lib/api/refus";
import {
  useConfirmedIdentityClubs,
  useDismissedIdentityCases,
  useIgnoredCourseDuplicates,
  useIgnoredIdentityPairs,
  useUnconfirmIdentityClub,
  useUndismissIdentityCase,
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
  note?: string;
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
  onUndo: (item: UndoItem) => void;
}) {
  return (
    <details className="group text-sm">
      <summary className="tcn-lien-action tcn-lien-action--tactile flex cursor-pointer list-none items-center gap-1 font-medium [&::-webkit-details-marker]:hidden">
        <ChevronRight size={14} aria-hidden="true" className="transition-transform group-open:rotate-90" />
        {`${title} (${items.length})`}
      </summary>
      {items.length === 0 ? (
        <p className="mt-2 text-[var(--tcn-text-faint)]">{empty}</p>
      ) : (
        <ul className="mt-2 divide-y">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                {item.label}
                {item.note && <span className="ml-2 text-[var(--tcn-text-faint)]">{item.note}</span>}
                {item.date && (
                  <span className="ml-2 text-[var(--tcn-text-faint)]">{`le ${formatDate(item.date)}`}</span>
                )}
              </span>
              <Button
                variant="outline"
                size="sm"
                aria-label={item.undoLabel}
                disabled={pending}
                onClick={() => onUndo(item)}
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

function notifyOutcome(message: string) {
  return {
    onSuccess: () => toast.success(message),
    onError: (error: Error) => toast.error(error.message),
  };
}

function fullName(person: { nom: string; prenom: string }): string {
  return `${person.nom} ${person.prenom}`;
}

const IDENTITY_REFUSAL = { sujet: "arbitrages d'identité", action: "revoir les arbitrages d'identité" };
const DUPLICATE_REFUSAL = { sujet: "paires écartées", action: "revoir les paires d'épreuves écartées" };

/** Paires écartées, cas à une fiche écartés et clubs confirmés de la revue d'identité. */
export function IdentityArbitrations() {
  const pairs = useIgnoredIdentityPairs();
  const cases = useDismissedIdentityCases();
  const clubs = useConfirmedIdentityClubs();
  const unignore = useUnignoreIdentityPair();
  const undismiss = useUndismissIdentityCase();
  const unconfirm = useUnconfirmIdentityClub();
  const confirm = useDangerConfirm();

  const error = pairs.error ?? cases.error ?? clubs.error;
  if (error) return <EmptyState {...messageDeRefus(error, IDENTITY_REFUSAL)} />;
  if (!pairs.data || !cases.data || !clubs.data) return null;

  /**
   * Annuler une mise à l'écart n'est pas un simple retour en revue : la reprise
   * fusionne d'elle-même deux fiches de même clé, et une fusion est sans retour.
   */
  async function undoPair(item: UndoItem) {
    const confirmed = await confirm({
      titre: `${item.undoLabel} ?`,
      description:
        "Si ces deux fiches portent la même clé d'identité, ou si la reprise les juge identiques, la prochaine reprise pourra fusionner les deux fiches, sans retour possible. Sinon, la paire reviendra dans la revue.",
      libelleAction: "Annuler la mise à l'écart",
    });
    if (confirmed) unignore.mutate(item.id, notifyOutcome("Mise à l'écart annulée."));
  }

  return (
    <div className="space-y-3">
      <UndoList
        title="Paires écartées"
        empty="Aucune paire écartée."
        pending={unignore.isPending}
        items={pairs.data.pairs.map((pair) => {
          const names = pair.athletes.map(fullName).join(" et ");
          return {
            id: pair.id,
            label: names,
            undoLabel: `Annuler la mise à l'écart de ${names}`,
            date: pair.ignored_at,
            note: pair.automatic ? "posée par l'import" : undefined,
          };
        })}
        onUndo={(item) => void undoPair(item)}
      />
      <UndoList
        title="Cas écartés"
        empty="Aucun cas écarté."
        pending={undismiss.isPending}
        items={cases.data.cases.map((dismissed) => ({
          id: dismissed.id,
          label: fullName(dismissed.athlete),
          undoLabel: `Annuler la mise à l'écart du cas de ${fullName(dismissed.athlete)}`,
          date: dismissed.dismissed_at,
          note: dismissed.reason_label,
        }))}
        onUndo={(item) =>
          undismiss.mutate(item.id, notifyOutcome("Mise à l'écart annulée : le cas revient dans la revue s'il tient toujours."))
        }
      />
      <UndoList
        title="Clubs confirmés"
        empty="Aucun club confirmé."
        pending={unconfirm.isPending}
        items={clubs.data.clubs.map((club) => ({
          id: club.id,
          label: `${fullName(club)} : ${club.club}`,
          undoLabel: `Annuler la confirmation de ${club.club} pour ${fullName(club)}`,
          date: club.confirmed_at,
        }))}
        onUndo={(item) =>
          unconfirm.mutate(item.id, notifyOutcome("La fiche sera de nouveau signalée pour ce club."))
        }
      />
    </div>
  );
}

/** Paires d'épreuves écartées de la liste des doublons suspects. */
export function IgnoredCourseDuplicates() {
  const { data, error } = useIgnoredCourseDuplicates();
  const unignore = useUnignoreCourseDuplicate();
  if (error) return <EmptyState {...messageDeRefus(error, DUPLICATE_REFUSAL)} />;
  if (!data) return null;

  return (
    <UndoList
      title="Paires écartées"
      empty="Aucune paire écartée."
      pending={unignore.isPending}
      items={data.pairs.map((pair) => {
        const names = pair.courses.map((course) => `${course.name} (n° ${course.id})`).join(" et ");
        return {
          id: pair.id,
          label: names,
          undoLabel: `Annuler la mise à l'écart de ${names}`,
          date: pair.ignored_at,
        };
      })}
      onUndo={(item) =>
        unignore.mutate(item.id, notifyOutcome("Mise à l'écart annulée : la paire revient dans la liste si elle reste suspecte."))
      }
    />
  );
}
