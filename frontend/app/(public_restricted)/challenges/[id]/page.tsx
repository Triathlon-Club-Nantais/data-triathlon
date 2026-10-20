import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { rendreNullSi404 } from "@/lib/api/null-si-404";
import { idDeRoute } from "@/lib/utils/id-de-route";
import { formatDate } from "@/lib/utils/date";
import { nonFinisherLabel } from "@/components/results/StatusBadge";
import { Card } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { SexeToggle } from "@/components/layout/SexeToggle";
import { EmptyState } from "@/components/ui/empty-state";
import { SEXE_PARAM, chezLesSexe, genderFromSexeParam } from "@/lib/scope";
import { plural } from "@/lib/utils/format";

export const metadata: Metadata = { title: "Classement Challenge" };

/**
 * Classement d'un Challenge (#1008) : le cumul de chaque athlète sur les épreuves
 * liées. Un vrai `<table>` natif, sans `.tcn-table` : trois colonnes ne
 * débordent pas un écran étroit, et la sémantique native suffit.
 */
export default async function ChallengePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { id } = await params;
  const gender = genderFromSexeParam((await searchParams)[SEXE_PARAM]);
  const challenge = await apiServer.getChallenge(idDeRoute(id), { gender }).catch(rendreNullSi404);
  if (!challenge) notFound();
  const unknown = challenge.unknown_gender_count ?? 0;
  const recalcules = !!gender && challenge.results.some((row) => row.gender_place_official === false);

  return (
    <PageShell>
      <PageHeader eyebrow="Classement Challenge" title={challenge.name} className="mb-6" />
      <div className="space-y-6">
        <Card>
          <p style={{ margin: 0 }}>
            {formatDate(challenge.event_date)}. Temps cumulé sur les épreuves :{" "}
            {challenge.courses.map((course, index) => (
              <span key={course.id}>
                {index > 0 && ", "}
                <Link href={`/courses/${course.id}`} className="underline underline-offset-2">
                  {course.name}
                </Link>
              </span>
            ))}
          </p>
        </Card>
        <Card>
          <div className="mb-4 space-y-2">
            <SexeToggle />
            {(recalcules || (!!gender && unknown > 0)) && (
              <div className="space-y-1 text-[13px]" style={{ color: "var(--tcn-text-muted)" }}>
                {recalcules && <p style={{ margin: 0 }}>Classement par sexe : places recalculées, la source ne publie pas toutes les places par sexe.</p>}
                {gender && unknown > 0 && (
                  <p style={{ margin: 0 }}>
                    {unknown} {plural(unknown, "résultat")} sans sexe connu,{" "}
                    {plural(unknown, "absent", "absents")} de ce classement.
                  </p>
                )}
              </div>
            )}
          </div>
          {gender && challenge.results.length === 0 ? (
            <EmptyState
              bare
              title={`Aucun classé ${chezLesSexe(gender)} sur ce challenge.`}
              action={
                <Link
                  href={`/challenges/${challenge.id}`}
                  className="tcn-cible-tactile inline-flex items-center text-sm font-semibold text-accent-ink hover:underline"
                >
                  Retirer le filtre par sexe
                </Link>
              }
            />
          ) : (
          <table className="w-full" aria-label="Classement du challenge">
            <thead>
              <tr>
                <th scope="col" className="text-left">{gender ? `Place (${gender === "M" ? "H" : "F"})` : "Rang"}</th>
                <th scope="col" className="text-left">Athlète</th>
                <th scope="col" className="text-right">Temps cumulé</th>
              </tr>
            </thead>
            <tbody>
              {challenge.results.map((row, index) => (
                // Une fusion de fiches peut réunir deux lignes sur un même athlète.
                <tr key={`${row.athlete_id}-${index}`}>
                  <td>{(gender ? row.gender_place : row.rank_overall) ?? nonFinisherLabel(row.status)}</td>
                  <td>
                    <Link href={`/athletes/${row.athlete_id}`} className="underline underline-offset-2">
                      {row.prenom} {row.nom}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums">{row.total_time ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </Card>
      </div>
    </PageShell>
  );
}
