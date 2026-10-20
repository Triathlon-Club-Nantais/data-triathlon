"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BestTimesCard } from "@/components/athletes/BestTimesCard";
import { Card, Eyebrow } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { RecapObjectifs } from "@/components/dashboard/RecapObjectifs";
import { useHydratedSession } from "@/lib/queries/auth";
import { isPodium } from "@/lib/utils/club-aggregate";
import { formatDate } from "@/lib/utils/date";
import { motCompte, ordinalFr } from "@/lib/utils/format";
import { seasonLabel, seasonOf } from "@/lib/utils/season";

/**
 * Récap d'une saison close de l'athlète rattaché (#1372) : ses seules lignes,
 * aucun classement d'autrui. Les chiffres suivent les règles déjà en place :
 * podium de Mon espace (`isPodium`), meilleurs temps de la fiche (#1361).
 */
export function SeasonRecap({ season, lastClosed }: { season: number; lastClosed: number }) {
  const session = useHydratedSession();
  const athlete = session.data?.athlete ?? null;
  const detail = useQuery({
    queryKey: ["season-recap", athlete?.id, season],
    queryFn: () => apiClient.getAthlete(athlete!.id, { seasons: String(season) }),
    enabled: athlete !== null,
    retry: false,
  });

  if (session.data === undefined) return null;
  if (athlete === null) {
    return (
      <Card>
        <p style={{ margin: 0 }}>
          Pour relire votre saison, rattachez votre fiche : « C&apos;est moi » sur votre fiche athlète, puis le club
          valide la demande.
        </p>
      </Card>
    );
  }

  const navigation = (
    <nav aria-label="Changer de saison" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
      <Link href={`/mon-espace/recap?saison=${season - 1}`} className="underline underline-offset-2">
        ← Saison précédente
      </Link>
      {season < lastClosed && (
        <Link href={`/mon-espace/recap?saison=${season + 1}`} className="underline underline-offset-2">
          Saison suivante →
        </Link>
      )}
    </nav>
  );

  if (detail.isPending) return navigation;
  if (detail.error) return <p role="alert">{detail.error.message}</p>;

  const resultats = detail.data.participations
    .filter((p) => !p.is_pending_validation)
    .sort((a, b) => (a.course.event_date ?? "").localeCompare(b.course.event_date ?? ""));
  const challenges = detail.data.challenges.filter((c) => seasonOf(c.event_date) === season);
  const podiums = resultats.filter((p) => isPodium(p)).length;

  return (
    <div style={{ display: "grid", gap: 24 }}>
      {navigation}
      <h2 style={{ margin: 0, fontFamily: "var(--tcn-font-display)", fontWeight: 400, fontSize: 26 }}>
        {seasonLabel(season)}
      </h2>
      {resultats.length === 0 ? (
        <>
          <Card>
            <p style={{ margin: 0 }}>Aucun résultat validé sur cette saison.</p>
          </Card>
          <RecapObjectifs season={season} />
        </>
      ) : (
        <>
          <Card>
            <Eyebrow>En chiffres</Eyebrow>
            <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0", display: "flex", gap: 32, flexWrap: "wrap" }}>
              <li style={{ fontSize: 22, fontWeight: 700 }}>{motCompte(resultats.length, "épreuve")}</li>
              <li style={{ fontSize: 22, fontWeight: 700 }}>{motCompte(podiums, "podium")}</li>
              {challenges.length > 0 && (
                <li style={{ fontSize: 22, fontWeight: 700 }}>{motCompte(challenges.length, "challenge")}</li>
              )}
            </ul>
          </Card>
          <RecapObjectifs season={season} />
          <BestTimesCard participations={resultats} />
          {challenges.length > 0 && (
            <Card>
              <Eyebrow>Challenges</Eyebrow>
              <ul style={{ margin: "12px 0 0", paddingLeft: 18 }}>
                {challenges.map((c) => (
                  <li key={c.id}>
                    <Link href={`/challenges/${c.id}`} className="underline underline-offset-2">{c.name}</Link>
                    {c.rank_overall ? ` : ${ordinalFr(c.rank_overall)} sur ${c.ranked_count}` : " : non classé"}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <Eyebrow>Mes épreuves</Eyebrow>
            <ul style={{ margin: "12px 0 0", paddingLeft: 18, display: "grid", gap: 6 }}>
              {resultats.map((p) => (
                <li key={p.id}>
                  <Link href={`/courses/${p.course.id}/participations/${p.id}`} className="underline underline-offset-2">
                    {formatDate(p.course.event_date)} {p.course.name}
                  </Link>
                  {p.total_time ? ` : ${p.total_time}` : ""}
                  {p.rank_overall ? `, ${ordinalFr(p.rank_overall)} au scratch` : ""}
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}
