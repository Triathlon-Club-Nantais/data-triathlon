"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Medal } from "@/components/ui/medal";
import { AnnonceStatut } from "@/components/tcn";
import { SportBadge } from "@/components/results/SportBadge";
import { formatEventName } from "@/lib/utils/event";
import { listPodiums } from "@/lib/utils/club-aggregate";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { podiumScopeLabel } from "@/lib/labels";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import type { Participation } from "@/lib/types";

/**
 * Taille de l'aperçu de la liste (#488, PROF-3). Le KPI « Podiums » deux blocs
 * plus haut annonce le total ; tronquer sans le dire faisait mentir la moitié
 * de l'écran. Le bouton d'extension dit combien il reste, et ouvre tout.
 */
export const APERCU_PODIUMS = 6;

/**
 * Liste des podiums récents côté client — lit `?rank=…` et recalcule
 * localement au changement, sans re-fetch. Le RSC parent fournit les
 * participations chargées une seule fois. Voir issue #132 (latence toggle).
 */
export function PodiumsList({ participations }: { participations: Participation[] }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const [etendu, setEtendu] = useState(false);
  const tous = useMemo(() => listPodiums(participations, rankType), [participations, rankType]);
  const podiums = etendu ? tous : tous.slice(0, APERCU_PODIUMS);
  const restants = tous.length - podiums.length;

  // WCAG 4.1.3 (#477) : la bascule recalcule en mémoire (#132), sans
  // navigation — sans cette annonce, la liste se réordonne (ou se vide) en
  // silence. Rendue avant le retour anticipé sur liste vide, à dessein : sinon
  // la région disparaît du DOM précisément quand un lecteur d'écran aurait le
  // plus besoin d'être prévenu.
  const annonce = (
    <AnnonceStatut texte={`${podiums.length} podium${podiums.length > 1 ? "s" : ""} affiché${podiums.length > 1 ? "s" : ""}`} />
  );

  if (podiums.length === 0) {
    return (
      <>
        {annonce}
        <p className="py-6 text-center text-sm text-[var(--tcn-text-faint)]">
          Pas encore de podium enregistré.
        </p>
      </>
    );
  }
  return (
    <>
      {annonce}
      <ul className="divide-y">
        {podiums.map(({ participation: p, best }) => {
          const name =
            [p.athlete.prenom, p.athlete.nom].filter(Boolean).join(" ") || "Athlète";
          const { Icon, label, title } = PODIUM_SCOPE_META[best.scope];
          return (
            <li key={p.id} className="flex items-center gap-3 py-2.5">
              <span className="relative inline-block">
                <Medal rank={best.rank} size={28} />
                <span
                  role="img"
                  aria-label={label}
                  title={title}
                  className="absolute -right-1 -bottom-1 inline-grid place-content-center rounded-full bg-background p-[1px] text-foreground"
                >
                  <Icon size={12} strokeWidth={2.5} aria-hidden="true" />
                </span>
              </span>
              <div className="min-w-0 flex-1">
                <Link
                  href={`/athletes/${p.athlete.id}`}
                  className="font-semibold hover:underline"
                >
                  {name}
                </Link>
                <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--tcn-text-faint)]">
                  <span className="truncate">{formatEventName(p.course.name, p.course.is_relay)}</span>
                  <SportBadge type={p.course.event_type} />
                  <span className="micro-label">{podiumScopeLabel(best.scope)}</span>
                </div>
              </div>
              {p.total_time && (
                <span className="num text-sm font-bold">{p.total_time}</span>
              )}
            </li>
          );
        })}
      </ul>
      {/* Bascule plutôt qu'un bouton qui se démonte : au clic, `restants`
          tombait à 0 et le `<button>` disparaissait du DOM — un utilisateur
          clavier perdait son focus au `<body>` et devait re-tabuler depuis le
          début du document pour atteindre les podiums qu'il venait de
          révéler, situés au-dessus (revue finale, #488). Le bouton reste
          monté tant qu'il y a quelque chose à réduire ou à étendre. */}
      {tous.length > APERCU_PODIUMS && (
        <button
          type="button"
          onClick={() => setEtendu((v) => !v)}
          aria-expanded={etendu}
          className="mt-3 text-sm font-medium text-accent-ink hover:underline"
        >
          {etendu
            ? "Réduire la liste"
            : restants > 1
              ? `Voir les ${restants} autres podiums`
              : "Voir l'autre podium"}
        </button>
      )}
    </>
  );
}
