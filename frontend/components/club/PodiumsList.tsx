"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Medal } from "@/components/ui/medal";
import { SportBadge } from "@/components/results/SportBadge";
import { formatEventName } from "@/lib/utils/event";
import { listPodiums, type PodiumScope } from "@/lib/utils/club-aggregate";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import type { Participation } from "@/lib/types";

const SCOPE_LABEL: Record<PodiumScope, string> = {
  overall: "Général",
  gender: "Genre",
  category: "Catégorie",
};

/**
 * Liste des podiums récents côté client — lit `?rank=…` et recalcule
 * localement au changement, sans re-fetch. Le RSC parent fournit les
 * participations chargées une seule fois. Voir issue #132 (latence toggle).
 */
export function PodiumsList({ participations }: { participations: Participation[] }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const podiums = useMemo(
    () => listPodiums(participations, rankType).slice(0, 6),
    [participations, rankType],
  );

  if (podiums.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Pas encore de podium enregistré.
      </p>
    );
  }
  return (
    <ul className="divide-y">
      {podiums.map(({ participation: p, best }) => {
        const name =
          [p.athlete?.prenom, p.athlete?.nom].filter(Boolean).join(" ") || "Athlète";
        return (
          <li key={p.id} className="flex items-center gap-3 py-2.5">
            <Medal rank={best.rank} size={28} />
            <div className="min-w-0 flex-1">
              <Link
                href={`/athletes/${p.athlete?.id}`}
                className="font-semibold hover:underline"
              >
                {name}
              </Link>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span className="truncate">{formatEventName(p.course.name, p.course.is_relay)}</span>
                <SportBadge type={p.course.event_type} />
                <span className="micro-label text-[9px]">{SCOPE_LABEL[best.scope]}</span>
              </div>
            </div>
            {p.total_time && (
              <span className="num text-sm font-bold">{p.total_time}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
