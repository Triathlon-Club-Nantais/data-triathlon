import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { rendreNullSi404 } from "@/lib/api/null-si-404";
import { idDeRoute } from "@/lib/utils/id-de-route";
import { formatDate } from "@/lib/utils/date";
import { Card } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";

export const metadata: Metadata = { title: "Classement Challenge" };

/**
 * Classement d'un Challenge (#1008) : le cumul de chaque athlète sur les épreuves
 * liées. Un vrai `<table>` natif, sans `.tcn-table` : trois colonnes ne
 * débordent pas un écran étroit, et la sémantique native suffit.
 */
export default async function ChallengePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const challenge = await apiServer.getChallenge(idDeRoute(id)).catch(rendreNullSi404);
  if (!challenge) notFound();

  return (
    <PageShell>
      <PageHeader eyebrow="Classement Challenge" title={challenge.name} />
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
          <table className="w-full" aria-label="Classement du challenge">
            <thead>
              <tr>
                <th scope="col" className="text-left">Rang</th>
                <th scope="col" className="text-left">Athlète</th>
                <th scope="col" className="text-right">Temps cumulé</th>
              </tr>
            </thead>
            <tbody>
              {challenge.results.map((row) => (
                <tr key={row.athlete_id}>
                  <td>{row.rank_overall ?? row.status}</td>
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
        </Card>
      </div>
    </PageShell>
  );
}
