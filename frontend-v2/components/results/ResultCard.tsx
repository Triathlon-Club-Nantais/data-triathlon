"use client";
import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SportBadge } from "./SportBadge";
import { splitSegments } from "@/lib/utils/splits";
import { formatDate, timeAgo } from "@/lib/utils/date";
import type { Participation } from "@/lib/types";

export function ResultCard({
  result,
  onDelete,
}: {
  result: Participation;
  onDelete?: (id: number) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const a = result.athlete;
  const c = result.course;
  const fullName = [a?.prenom, a?.nom].filter(Boolean).join(" ") || "Athlète inconnu";
  const segments = splitSegments(c?.event_type ?? "", result.splits);

  function handleDelete() {
    if (!onDelete) return;
    if (confirming) {
      onDelete(result.id);
    } else {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 3000);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link href={`/athletes/${a.id}`} className="text-lg font-bold hover:underline">
              {fullName}
            </Link>
            <div className="mt-1 flex flex-wrap gap-2 text-sm text-muted-foreground">
              {result.club && <span>{result.club}</span>}
              {result.category && <Badge variant="outline">{result.category}</Badge>}
              {a?.gender && <Badge variant="outline">{a.gender}</Badge>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {result.total_time && (
              <span className="font-mono text-xl font-extrabold">{result.total_time}</span>
            )}
            {onDelete && (
              <Button
                variant={confirming ? "destructive" : "ghost"}
                size="sm"
                onClick={handleDelete}
                aria-label={confirming ? "Confirmer la suppression" : "Supprimer"}
              >
                {confirming ? "Confirmer ?" : "×"}
              </Button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-b pb-3 text-sm">
          <Link href={`/courses/${c.id}`} className="font-semibold hover:underline">
            {c?.name || "Épreuve inconnue"}
          </Link>
          <SportBadge type={c?.event_type} />
          {c?.event_date && (
            <span className="text-muted-foreground">{formatDate(c.event_date)}</span>
          )}
          {result.bib_number && (
            <span className="text-muted-foreground">#{result.bib_number}</span>
          )}
          {c?.is_relay && <Badge variant="destructive">Relais</Badge>}
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
                <span className="text-xs font-bold uppercase" style={{ color: s.color }}>
                  {s.label}
                </span>
                <span className="font-mono text-sm font-semibold">{s.time}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <a href={c?.source_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
            Source ({c?.provider})
          </a>
          {result.created_at && <span>Ajouté {timeAgo(result.created_at)}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function Rank({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-[11px] font-semibold uppercase text-muted-foreground">{label}</span>
      <span className="text-xl font-extrabold">{value}e</span>
    </div>
  );
}
