"use client";
import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Medal } from "@/components/ui/medal";
import { AnnonceStatut } from "@/components/tcn";
import { SportBadge } from "@/components/results/SportBadge";
import { formatEventName } from "@/lib/utils/event";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { podiumScopeLabel } from "@/lib/labels";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import type { ClubPodiums } from "@/lib/types";

/**
 * Taille de l'aperçu de la liste (#488, PROF-3). Le KPI « Podiums » deux blocs
 * plus haut annonce le total ; tronquer sans le dire faisait mentir la moitié
 * de l'écran. Le bouton d'extension dit combien il reste, et ouvre tout.
 */
export const APERCU_PODIUMS = 6;

/**
 * Liste des podiums récents côté client — lit `?rank=…` et sélectionne le
 * bucket déjà calculé côté serveur (#581), sans re-fetch. Voir issue #132
 * (latence toggle) : le mécanisme de bascule est inchangé, seul le payload a
 * changé de forme (un `ClubPodiums` pré-agrégé au lieu du tableau complet des
 * participations).
 */
export function PodiumsList({ podiums }: { podiums: ClubPodiums }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const [etendu, setEtendu] = useState(false);
  const tous = podiums[rankType];
  const affiches = etendu ? tous : tous.slice(0, APERCU_PODIUMS);
  const restants = tous.length - affiches.length;

  // WCAG 4.1.3 (#477) : la bascule recalcule en mémoire (#132), sans
  // navigation — sans cette annonce, la liste se réordonne (ou se vide) en
  // silence. Rendue avant le retour anticipé sur liste vide, à dessein : sinon
  // la région disparaît du DOM précisément quand un lecteur d'écran aurait le
  // plus besoin d'être prévenu.
  const annonce = (
    <AnnonceStatut texte={`${affiches.length} podium${affiches.length > 1 ? "s" : ""} affiché${affiches.length > 1 ? "s" : ""}`} />
  );

  if (affiches.length === 0) {
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
        {affiches.map((p) => {
          const { Icon, label, title } = PODIUM_SCOPE_META[p.scope];
          return (
            <li key={p.participation_id} className="flex items-center gap-3 py-2.5">
              <span className="relative inline-block">
                <Medal rank={p.rank} size={28} />
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
                <Link href={`/athletes/${p.athlete_id}`} className="font-semibold hover:underline">
                  {p.athlete_name}
                </Link>
                <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--tcn-text-faint)]">
                  <span className="truncate">{formatEventName(p.event_name, p.is_relay)}</span>
                  <SportBadge type={p.event_type} />
                  <span className="micro-label">{podiumScopeLabel(p.scope)}</span>
                </div>
              </div>
              {p.total_time && <span className="num text-sm font-bold">{p.total_time}</span>}
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
