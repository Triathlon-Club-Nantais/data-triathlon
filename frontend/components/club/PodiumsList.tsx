"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Medal } from "@/components/ui/medal";
import { AnnonceStatut } from "@/components/tcn";
import { SportBadge } from "@/components/results/SportBadge";
import { formatEventName } from "@/lib/utils/event";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { podiumScopeLabel } from "@/lib/labels";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import { SPORTS_PARAM, federalOnlyFromParam } from "@/lib/scope";
import { apiClient } from "@/lib/api/client";
import type { ClubPodiumTotals, ClubPodiums } from "@/lib/types";
import { currentSeason, selectedSeasonsOrCurrent } from "@/lib/utils/season";
import { motCompte, plural } from "@/lib/utils/format";

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
 *
 * `/club` n'en reçoit que l'aperçu et les `totals` (#1354) : la liste complète
 * se charge au premier dépliage, une fois pour les quatre modes. La clé sur
 * `?sports=` remonte la liste quand le filtre change : `router.push` garde le
 * composant monté, et la liste chargée sous l'autre filtre survivrait sinon.
 */
export function PodiumsList(props: { podiums: ClubPodiums; totals?: ClubPodiumTotals }) {
  const sp = useSearchParams();
  return <Podiums key={`${sp.get(SPORTS_PARAM) ?? ""}|${sp.get("seasons") ?? ""}`} {...props} />;
}

function Podiums({ podiums, totals }: { podiums: ClubPodiums; totals?: ClubPodiumTotals }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const selectedSeasons = selectedSeasonsOrCurrent(sp.get("seasons"));
  const [etendu, setEtendu] = useState(false);
  const [complet, setComplet] = useState<ClubPodiums | null>(null);
  const [chargement, setChargement] = useState(false);
  const [echec, setEchec] = useState(false);
  // Un double clic arrive avant le rendu qui poserait `chargement`.
  const enVol = useRef(false);
  const tous = (complet ?? podiums)[rankType];
  const total = complet ? tous.length : (totals?.[rankType] ?? tous.length);
  const affiches = etendu ? tous : tous.slice(0, APERCU_PODIUMS);
  const restants = total - affiches.length;

  async function basculer() {
    if (enVol.current) return;
    if (!etendu && !complet && total > tous.length) {
      enVol.current = true;
      setChargement(true);
      setEchec(false);
      try {
        setComplet(await apiClient.getClubPodiums({
          federal_only: federalOnlyFromParam(sp.get(SPORTS_PARAM)),
          seasons: selectedSeasons,
        }));
        setEtendu(true);
      } catch {
        setEchec(true);
      } finally {
        enVol.current = false;
        setChargement(false);
      }
      return;
    }
    setEtendu((v) => !v);
  }

  // WCAG 4.1.3 (#477) : la bascule recalcule en mémoire (#132), sans
  // navigation — sans cette annonce, la liste se réordonne (ou se vide) en
  // silence. Rendue avant le retour anticipé sur liste vide, à dessein : sinon
  // la région disparaît du DOM précisément quand un lecteur d'écran aurait le
  // plus besoin d'être prévenu.
  const annonce = (
    <AnnonceStatut
      texte={
        chargement
          ? "Chargement des podiums…"
          : `${motCompte(affiches.length, "podium")} ${plural(affiches.length, "affiché")}`
      }
    />
  );

  if (affiches.length === 0) {
    return (
      <>
        {annonce}
        <p className="py-6 text-center text-sm text-[var(--tcn-text-faint)]">
          {selectedSeasons.includes(currentSeason()) ? "Pas encore de podium enregistré." : "Aucun podium enregistré."}
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
                {/* Un podium de relais reste une entrée (#894) : le lien mène au
                    porteur, les autres équipiers sont nommés à côté. */}
                {(p.teammate_names ?? []).length > 1 && (
                  <span className="ml-1 text-sm text-[var(--tcn-text-muted)]">
                    {`avec ${(p.teammate_names ?? []).filter((n) => n !== p.athlete_name).join(", ")}`}
                  </span>
                )}
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
      {echec && (
        <p role="alert" className="mt-3 text-sm text-[var(--tcn-danger-text)]">
          Les autres podiums n&apos;ont pas pu être chargés. Réessayez avec le bouton ci-dessous.
        </p>
      )}
      {total > APERCU_PODIUMS && (
        <button
          type="button"
          onClick={basculer}
          aria-expanded={etendu}
          aria-busy={chargement}
          // Seul moyen de relancer après un échec : 44 px au doigt (#1378).
          className="mt-3 inline-flex min-h-11 items-center text-sm font-medium text-accent-ink hover:underline"
        >
          {chargement
            ? "Chargement des podiums…"
            : etendu
            ? "Réduire la liste"
            : restants > 1
              ? `Voir les ${restants} autres podiums`
              : "Voir l'autre podium"}
        </button>
      )}
    </>
  );
}
