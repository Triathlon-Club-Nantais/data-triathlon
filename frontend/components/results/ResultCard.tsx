"use client";
import Link from "next/link";
import { Avatar } from "@/components/tcn";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SportBadge } from "./SportBadge";
import { StatusBadge } from "./StatusBadge";
import { Medal } from "@/components/ui/medal";
import { splitSegments } from "@/lib/utils/splits";
import { inkColor } from "@/lib/sport-colors";
import { formatDate, timeAgo } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";
import type { Participation } from "@/lib/types";

export function ResultCard({ result }: { result: Participation }) {
  const a = result.athlete;
  const c = result.course;
  const fullName = [a?.prenom, a?.nom].filter(Boolean).join(" ") || "Athlète inconnu";
  const segments = splitSegments(c?.event_type ?? "", result.splits);

  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Avatar name={fullName} size={38} style={{ marginTop: 2 }} />
            <div>
              <Link href={`/athletes/${a.id}`} className="text-lg font-bold hover:underline">
                {fullName}
              </Link>
              <div className="mt-1 flex flex-wrap gap-2 text-sm text-[var(--tcn-text-faint)]">
                {result.club && <span>{result.club}</span>}
                {result.category && <Badge variant="outline">{result.category}</Badge>}
                {a?.gender && <Badge variant="outline">{a.gender}</Badge>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {result.total_time ? (
              <span className="num text-xl font-extrabold">{result.total_time}</span>
            ) : (
              <StatusBadge status={result.status} />
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-b pb-3 text-sm">
          <Link href={`/courses/${c.id}`} className="font-semibold hover:underline">
            {c?.name ? formatEventName(c.name, c.is_relay) : "Épreuve inconnue"}
          </Link>
          <SportBadge type={c?.event_type} />
          {c?.event_date && (
            <span className="text-[var(--tcn-text-faint)]">{formatDate(c.event_date)}</span>
          )}
          {result.bib_number && (
            <span className="text-[var(--tcn-text-faint)]">#{result.bib_number}</span>
          )}
          {(result.is_relay || c?.is_relay) && <Badge variant="destructive">Relais</Badge>}
        </div>

        {(result.rank_overall || result.rank_category || result.rank_gender) && (
          <div className="flex gap-6">
            {result.rank_overall != null && <Rank label="Général" value={result.rank_overall} />}
            {result.rank_gender != null && <Rank label="Genre" value={result.rank_gender} />}
            {result.rank_category != null && <Rank label="Catégorie" value={result.rank_category} />}
          </div>
        )}

        {segments.length > 0 && (
          <div className="flex flex-wrap gap-3 rounded-md bg-muted px-4 py-3">
            {segments.map((s) => (
              <div
                key={s.key}
                className="flex min-w-[60px] flex-col items-center"
                style={{ opacity: s.small ? 0.6 : 1 }}
              >
                <span className="micro-label" style={{ color: inkColor(s.color) }}>
                  {s.label}
                </span>
                <span className="num text-sm font-semibold">{s.time}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-[var(--tcn-text-faint)]">
          {isHttpUrl(c?.source_url) ? (
            <a href={c?.source_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
              Source ({c?.provider})
            </a>
          ) : (
            <span>Source ({c?.provider})</span>
          )}
          {result.created_at && <span>Ajouté {timeAgo(result.created_at)}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function Rank({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="micro-label text-[var(--tcn-text-faint)]">{label}</span>
      {value <= 3 ? (
        <Medal rank={value} size={26} />
      ) : (
        <span className="num text-xl font-extrabold">
          {value}
          <span className="align-super text-xs">ᵉ</span>
        </span>
      )}
    </div>
  );
}
