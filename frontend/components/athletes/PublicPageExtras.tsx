import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { eventTypeLabel } from "@/lib/constants";
import type { Participation, PublicLink, SeasonGoal } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { ordinalFr } from "@/lib/utils/format";
import { libelle, progression } from "@/lib/utils/season-goal";

/** Les libellés viennent du serveur (jamais saisis) ; `url` est validée côté API. */
export function PublicLinks({ links }: { links: PublicLink[] }) {
  if (links.length === 0) return null;
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 text-sm">
      {links.map((link) => (
        <li key={link.url}>
          <a
            href={link.url}
            target="_blank"
            rel="noopener nofollow ugc"
            className="underline underline-offset-2 text-[var(--tcn-orange-deeper)]"
          >
            {link.label}
            {" "}
            <span className="sr-only">(nouvel onglet)</span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export function PublicGoal({ goal }: { goal: SeasonGoal }) {
  return (
    <div className="pt-2 text-sm">
      <span className="font-semibold text-[var(--tcn-text-faint)]">Objectif de la saison</span>
      <div className="font-bold">{libelle(goal)}</div>
      <div className="text-[var(--tcn-text-muted)]">{progression(goal)}</div>
    </div>
  );
}

export function PinnedResult({ participation }: { participation: Participation }) {
  const { course } = participation;
  return (
    <Card>
      <Eyebrow>Résultat épinglé</Eyebrow>
      <Link
        href={`/courses/${course.id}/participations/${participation.id}`}
        className="mt-2 block underline underline-offset-2"
      >
        {course.name}
        {course.event_date ? `, ${formatDate(course.event_date)}` : ""} ({eventTypeLabel(course.event_type)})
      </Link>
      <p className="mt-1 text-sm text-[var(--tcn-text-faint)]">
        {[participation.total_time, participation.rank_overall != null ? `${ordinalFr(participation.rank_overall)} au général` : null]
          .filter(Boolean)
          .join(", ")}
      </p>
    </Card>
  );
}
