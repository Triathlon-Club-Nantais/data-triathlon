"use client";
import Link from "next/link";
import { Avatar, VousChip } from "@/components/tcn";
import { useSelectedAthlete } from "@/components/layout/AthletePicker";
import { trouverRang } from "@/lib/utils/rang";
import type { PodiumScope, RosterEntry } from "@/lib/utils/club-aggregate";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import { RappelPosition } from "./RappelPosition";

/**
 * Aperçu du roster (#487) et sa fiche mise en avant (#504) : bloc client
 * monté au-dessus du reste, purement serveur, de `ClubDashboard` — même
 * raison que `ClubPodiumKpi`/`PodiumsList`, qui recalculent déjà en mémoire à
 * partir de props sérialisées plutôt que de re-fetcher.
 */
export function RosterApercu({
  roster,
  apercuTaille,
}: {
  roster: RosterEntry[];
  apercuTaille: number;
}) {
  const athleteRetenu = useSelectedAthlete();
  const rang = athleteRetenu
    ? trouverRang(athleteRetenu.id, roster.map((r) => r.athleteId))
    : null;
  const rappelVisible = rang !== null && rang > apercuTaille;
  const apercu = roster.slice(0, apercuTaille);

  return (
    <>
      <RappelPosition
        visible={rappelVisible}
        epreuves={rang ? roster[rang - 1].count : 0}
        rang={rang ?? 0}
        hrefAncre={athleteRetenu ? `/club/athletes#athlete-${athleteRetenu.id}` : "#"}
      />
      {apercu.some((r) => r.podiums > 0) && (
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Les podiums comptés ici cumulent le général, le genre et la catégorie.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {apercu.map((r) => {
          const moi = athleteRetenu?.id === r.athleteId;
          return (
            <Link
              key={r.athleteId}
              href={`/athletes/${r.athleteId}`}
              className={
                moi
                  ? "flex items-center gap-3 rounded-xl p-3 ring-1 ring-foreground/10 transition-colors tcn-roster-card--moi"
                  : "flex items-center gap-3 rounded-xl bg-card p-3 ring-1 ring-foreground/10 transition-colors hover:bg-muted/50"
              }
            >
              <Avatar name={r.name} size={40} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 truncate font-semibold">
                  <span className="truncate">{r.name}</span>
                  {moi && <VousChip />}
                </div>
                <div className="text-xs text-[var(--tcn-text-faint)]">
                  {r.count} épreuve{r.count > 1 ? "s" : ""}
                  {r.podiums > 0 && ` · ${r.podiums} podium${r.podiums > 1 ? "s" : ""}`}
                </div>
              </div>
              {r.podiums > 0 && <RosterPodiumBadges roster={r} />}
            </Link>
          );
        })}
      </div>
    </>
  );
}

/**
 * Podiums d'un athlète du roster, ventilés par scope (#128). Une icône +
 * décompte par scope non nul, chacun avec le tooltip natif partagé — permet
 * de distinguer « 3 podiums scratch » de « 3 podiums de catégorie » là où
 * l'ancien `🏅3` amalgamait tout.
 */
function RosterPodiumBadges({ roster }: { roster: RosterEntry }) {
  const scopes: PodiumScope[] = ["overall", "gender", "category"];
  return (
    <span className="flex shrink-0 items-center gap-1.5">
      {scopes.map((scope) => {
        const n = roster.podiumsByScope[scope];
        if (n === 0) return null;
        const { Icon, label, title } = PODIUM_SCOPE_META[scope];
        return (
          <span
            key={scope}
            className="num inline-flex items-center gap-0.5 text-sm font-bold text-accent-ink"
            title={`${n} ${title.toLowerCase()}`}
            aria-label={`${n} ${label.toLowerCase()}`}
          >
            <Icon size={14} strokeWidth={2.5} aria-hidden="true" />
            {n}
          </span>
        );
      })}
    </span>
  );
}
