import { Medal, Users } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/tcn/Card";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import { eventTypeLabel } from "@/lib/constants";
import { estToutRecent, titreSortie } from "@/lib/home";
import type { ClubLastOuting, Stats } from "@/lib/types";
import { formatCount, motCompte } from "@/lib/utils/format";
import { currentSeason, seasonAbsenceLabel, seasonSelectionLabel } from "@/lib/utils/season";
import { HistogrammeMois } from "@/components/charts/HistogrammeMois";
import { ChiffreAnime } from "./ChiffreAnime";

const display = { fontFamily: "var(--tcn-font-display)", fontWeight: 400, lineHeight: 1 } as const;

function Chiffre({ valeur, libelle }: { valeur: number; libelle: string }) {
  return (
    <div style={{ color: "var(--tcn-ink)" }}>
      <div style={{ ...display, fontSize: 28 }}>{formatCount(valeur)}</div>
      <div style={{ fontSize: 13, fontWeight: 700 }}>{libelle}</div>
    </div>
  );
}

const LIGNES_BUREAU = 3;
const LIGNES_MOBILE = 2;

/** « triathlon-m » se lit « M » dans une pastille ; les autres types gardent leur libellé. */
function pastilleFormat(type: string): string {
  const format = /-(xxs|xs|s|m|l|xl|xxl)$/.exec(type);
  return format ? format[1].toUpperCase() : eventTypeLabel(type);
}

function LignesEpreuves({ courses, resultatsHref }: { courses: ClubLastOuting["courses"]; resultatsHref: string }) {
  if (courses.length === 0) return null;
  const restantesBureau = courses.length - LIGNES_BUREAU;
  const restantesMobile = courses.length - LIGNES_MOBILE;
  return (
    <ul style={{ listStyle: "none", margin: "16px 0 0", padding: 0, display: "grid", gap: 4 }}>
      {courses.slice(0, LIGNES_BUREAU).map((course, i) => (
        <li key={course.id}>
          <Link
            href={`/courses/${course.id}`}
            className={`tcn-ligne-sortie ${i >= LIGNES_MOBILE ? "hidden md:flex" : "flex"} items-center gap-3 rounded-xl px-1`}
            style={{ minHeight: 44, color: "#fff", textDecoration: "none" }}
          >
            <span style={{ flex: "none", minWidth: 32, textAlign: "center", padding: "2px 8px", borderRadius: 999, background: "#fff", color: "var(--tcn-orange-deeper)", fontSize: 12, fontWeight: 800 }}>
              {pastilleFormat(course.event_type)}
            </span>
            <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 700 }}>{course.name}</span>
            <span className="inline-flex items-center gap-1" style={{ flex: "none", fontWeight: 800 }}>
              <Users aria-hidden="true" size={16} />
              <span aria-hidden="true">{course.tcn}</span>
              <span className="sr-only">{motCompte(course.tcn, "athlète")} du club</span>
            </span>
            {course.podiums > 0 && (
              <span data-podiums className="inline-flex items-center gap-1" style={{ flex: "none" }}>
                <Medal aria-hidden="true" size={16} />
                <span aria-hidden="true">{course.podiums}</span>
                <span className="sr-only">{motCompte(course.podiums, "podium")}</span>
              </span>
            )}
            <span aria-hidden="true">→</span>
          </Link>
        </li>
      ))}
      {restantesMobile > 0 && (
        <li>
          <Link
            href={resultatsHref}
            className={`tcn-ligne-sortie flex items-center rounded-xl px-1 font-bold underline ${restantesBureau > 0 ? "" : "md:hidden"}`}
            style={{ minHeight: 44, color: "#fff" }}
          >
            <span className="md:hidden">et {motCompte(restantesMobile, "autre")} {restantesMobile > 1 ? "épreuves" : "épreuve"} →</span>
            {restantesBureau > 0 && <span className="hidden md:inline">et {motCompte(restantesBureau, "autre")} {restantesBureau > 1 ? "épreuves" : "épreuve"} →</span>}
          </Link>
        </li>
      )}
    </ul>
  );
}

/** Le pouls du club en tête d'accueil (#1621) : carte de la dernière sortie, carte de la saison. */
export function BandeauDirect({ sortie, stats, seasons, today, resultatsHref }: { sortie: ClubLastOuting | null; stats: Stats; seasons: number[]; today: Date; resultatsHref: string }) {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <section
        aria-label="Dernière sortie"
        className="tcn-carte-sortie"
        style={{ minWidth: 0, background: "var(--tcn-orange-grad)", color: "#fff", borderRadius: "var(--tcn-radius-3xl)", padding: "24px clamp(18px, 4vw, 32px)", boxShadow: "var(--tcn-shadow-orange-lg)" }}
      >
        <div className="tcn-carte-sortie-contenu">
        {sortie ? (
          <>
            <h2 style={{ margin: 0, fontSize: "inherit", fontWeight: 800, display: "flex", alignItems: "center", gap: 10 }}>
              {titreSortie(sortie.end_date, today)}
              {estToutRecent(sortie.end_date, today) && <span aria-hidden="true" className="tcn-pouls" />}
            </h2>
            <p style={{ ...display, margin: "6px 0 0", fontSize: "clamp(40px, 9vw, 64px)" }}>
              <ChiffreAnime valeur={sortie.athletes} /> {CLUB_NAME_SHORT}
            </p>
            <p style={{ margin: "6px 0 0", fontWeight: 700 }}>
              {motCompte(sortie.events, "épreuve")} · {motCompte(sortie.podiums, "podium")}
            </p>
            <LignesEpreuves courses={sortie.courses} resultatsHref={resultatsHref} />
          </>
        ) : (
          <p style={{ ...display, margin: 0, fontSize: 28 }}>{seasons.length === 1 && seasons[0] === currentSeason() ? "Pas encore d'épreuve cette saison" : `Aucune épreuve pour ${seasonAbsenceLabel(seasons)}`}</p>
        )}
        </div>
      </section>
      <section aria-labelledby="bandeau-saison-titre" style={{ minWidth: 0 }}>
        <Card padding="24px clamp(18px, 4vw, 32px)" style={{ height: "100%", minWidth: 0 }}>
          <h1 id="bandeau-saison-titre" style={{ margin: 0, fontSize: 12, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--tcn-text-muted)" }}>
            {CLUB_NAME} · {seasonSelectionLabel(seasons)}
          </h1>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 16 }}>
            <Chiffre valeur={stats.total} libelle="résultats" />
            <Chiffre valeur={stats.athletes} libelle="athlètes" />
            <Chiffre valeur={stats.rank_counters.all.podiums} libelle="podiums" />
          </div>
          <div style={{ marginTop: 20 }}>
            <HistogrammeMois byMonth={stats.by_month} seasons={seasons} />
          </div>
        </Card>
      </section>
    </div>
  );
}
