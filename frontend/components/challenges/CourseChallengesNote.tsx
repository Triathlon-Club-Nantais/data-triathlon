import Link from "next/link";
import { Card } from "@/components/tcn";
import type { CourseChallenge } from "@/lib/types";

/** Les classements Challenge auxquels compte l'épreuve (#1008). */
export function CourseChallengesNote({ challenges }: { challenges: CourseChallenge[] }) {
  if (challenges.length === 0) return null;
  return (
    <Card style={{ marginBottom: 18 }}>
      <p style={{ margin: 0 }}>
        Cette épreuve compte pour :{" "}
        {challenges.map((challenge, index) => (
          <span key={challenge.id}>
            {index > 0 && ", "}
            <Link href={`/challenges/${challenge.id}`} className="underline underline-offset-2">
              {challenge.name}
            </Link>{" "}
            ({challenge.ranked_count} {challenge.ranked_count > 1 ? "classés" : "classé"})
          </span>
        ))}
      </p>
    </Card>
  );
}
