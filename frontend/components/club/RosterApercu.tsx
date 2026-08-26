"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Avatar, VousChip } from "@/components/tcn";
import { useSelectedAthlete } from "@/components/layout/AthletePicker";
import { useClubRosterRank } from "@/lib/queries/club";
import { SPORTS_PARAM, federalOnlyFromParam } from "@/lib/scope";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import type { PodiumScope } from "@/lib/podium-scope";
import type { ClubRosterEntry } from "@/lib/types";

/**
 * Aperçu du roster (#487) et sa mise en avant (#504) : bloc client monté
 * au-dessus du reste, purement serveur, de `ClubDashboard` — même raison que
 * `ClubPodiumKpi`/`PodiumsList`, qui recalculent déjà en mémoire à partir de
 * props sérialisées plutôt que de re-fetcher.
 *
 * `roster` arrive déjà plafonné à 12 côté SQL (#581,
 * `athlete_repository.club_roster`) : rien ici ne permet de calculer un rang
 * exact au-delà de l'aperçu **sans requête** — contrairement à
 * `AthleteSeasonList` (#274, liste complète d'une saison). `useClubRosterRank`
 * (#641) le demande donc à la demande, seulement quand l'athlète retenu en
 * sort ; tant qu'il n'a pas répondu (ou si l'athlète est hors roster — `null`,
 * un état normal), le rappel reste générique, sans numéro de rang.
 */
export function RosterApercu({ roster }: { roster: ClubRosterEntry[] }) {
  const athleteRetenu = useSelectedAthlete();
  const horsApercu = athleteRetenu != null && !roster.some((r) => r.athlete_id === athleteRetenu.id);
  const sp = useSearchParams();
  const federalOnly = federalOnlyFromParam(sp.get(SPORTS_PARAM)) ?? false;
  const { data: classement } = useClubRosterRank(athleteRetenu?.id ?? 0, {
    federalOnly,
    enabled: horsApercu,
  });

  return (
    <>
      <div className="min-h-11">
        {horsApercu && (
          <Link
            href={`/club/athletes#athlete-${athleteRetenu.id}`}
            className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold"
            style={{
              background: "var(--tcn-orange-08)",
              border: "1px solid rgba(233,83,14,.25)",
              color: "var(--tcn-orange-deeper)",
            }}
          >
            {classement
              ? `Vous : ${classement.rank}ᵉ des ${classement.total} athlètes du club`
              : `Vous n'êtes pas parmi les ${roster.length} athlètes les plus actifs`}{" "}
            — Voir tous les athlètes →
          </Link>
        )}
      </div>
      {roster.some((r) => r.podiums > 0) && (
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Les podiums comptés ici cumulent le général, le genre et la catégorie.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {roster.map((r) => {
          const name = `${r.prenom} ${r.nom}`;
          const moi = athleteRetenu?.id === r.athlete_id;
          return (
            <Link
              key={r.athlete_id}
              href={`/athletes/${r.athlete_id}`}
              className={
                moi
                  ? "flex items-center gap-3 rounded-xl p-3 ring-1 ring-foreground/10 transition-colors tcn-roster-card--moi"
                  : "flex items-center gap-3 rounded-xl bg-card p-3 ring-1 ring-foreground/10 transition-colors hover:bg-muted/50"
              }
            >
              <Avatar name={name} size={40} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 truncate font-semibold">
                  <span className="truncate">{name}</span>
                  {moi && <VousChip />}
                </div>
                <div className="text-xs text-[var(--tcn-text-faint)]">
                  {r.count} épreuve{r.count > 1 ? "s" : ""}
                  {r.podiums > 0 && ` · ${r.podiums} podium${r.podiums > 1 ? "s" : ""}`}
                </div>
              </div>
              {r.podiums > 0 && (
                <RosterPodiumBadges
                  overall={r.podiums_overall}
                  gender={r.podiums_gender}
                  category={r.podiums_category}
                />
              )}
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
function RosterPodiumBadges({
  overall,
  gender,
  category,
}: {
  overall: number;
  gender: number;
  category: number;
}) {
  const values: Record<PodiumScope, number> = { overall, gender, category };
  const scopes: PodiumScope[] = ["overall", "gender", "category"];
  return (
    <span className="flex shrink-0 items-center gap-1.5">
      {scopes.map((scope) => {
        const n = values[scope];
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
