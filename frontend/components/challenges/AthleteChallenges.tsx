import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { formatDate } from "@/lib/utils/date";
import { ordinalFr } from "@/lib/utils/format";
import type { AthleteChallenge } from "@/lib/types";

/**
 * Classements Challenge de l'athlète (#1008) : un cumul sur plusieurs épreuves
 * du même jour. Hors de toute tuile et de tout graphique de la fiche, qui ne
 * lisent que les participations.
 */
export function AthleteChallenges({ challenges }: { challenges: AthleteChallenge[] }) {
  if (challenges.length === 0) return null;
  return (
    <Card>
      <Eyebrow role="heading" aria-level={2} id="titre-challenges">
        Challenges
      </Eyebrow>
      <ul aria-labelledby="titre-challenges" style={{ listStyle: "none", padding: 0, margin: "12px 0 0" }}>
        {challenges.map((challenge) => (
          <li key={challenge.id} style={{ marginTop: 10 }}>
            <Link href={`/challenges/${challenge.id}`} className="underline underline-offset-2">
              {challenge.name}
            </Link>
            <span style={{ color: "var(--tcn-text-faint)" }}> ({formatDate(challenge.event_date)})</span>
            <div>
              {challenge.rank_overall !== null && (
                <span>
                  {ordinalFr(challenge.rank_overall)} / {challenge.ranked_count}
                  {challenge.total_time ? ", " : ""}
                </span>
              )}
              {challenge.total_time && <span>{challenge.total_time}</span>}
            </div>
            {challenge.courses.length > 0 && (
              <div style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
                Épreuves :{" "}
                {challenge.courses.map((course, index) => (
                  <span key={course.id}>
                    {index > 0 && ", "}
                    <Link href={`/courses/${course.id}`} className="underline underline-offset-2">
                      {course.name}
                    </Link>
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
