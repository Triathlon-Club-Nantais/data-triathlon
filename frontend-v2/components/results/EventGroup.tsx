"use client";
import { useMemo } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { ResultCard } from "./ResultCard";
import { SportBadge } from "./SportBadge";
import { formatDate } from "@/lib/utils/date";
import { isTCN } from "@/lib/utils/club";
import type { Participation } from "@/lib/types";

interface Group {
  key: string;
  name: string;
  date: string | null;
  type: string;
  items: Participation[];
  tcnCount: number;
}

export function EventGroup({
  participations,
  onDelete,
}: {
  participations: Participation[];
  onDelete?: (id: number) => void;
}) {
  const groups = useMemo<Group[]>(() => {
    const map = new Map<string, Group>();
    for (const p of participations) {
      const name = p.course?.name ?? "Épreuve inconnue";
      const date = p.course?.event_date ?? null;
      const type = p.course?.event_type ?? "";
      const isRelay = Boolean(p.course?.is_relay);
      const key = `${name}||${date ?? ""}||${type}||${isRelay ? "relay" : "solo"}`;
      let g = map.get(key);
      if (!g) {
        g = { key, name, date, type, items: [], tcnCount: 0 };
        map.set(key, g);
      }
      g.items.push(p);
      if (isTCN(p.club)) g.tcnCount += 1;
    }
    return [...map.values()].sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
  }, [participations]);

  if (groups.length === 0) {
    return <p className="py-10 text-center text-muted-foreground">Aucun résultat.</p>;
  }

  return (
    <Accordion defaultValue={groups.map((g) => g.key)} className="space-y-2">
      {groups.map((g) => (
        <AccordionItem key={g.key} value={g.key} className="rounded-md border px-4">
          <AccordionTrigger>
            <div className="flex flex-1 flex-wrap items-center gap-3 pr-4 text-left">
              <span className="font-semibold">{g.name}</span>
              <SportBadge type={g.type} />
              {g.date && <span className="text-sm text-muted-foreground">{formatDate(g.date)}</span>}
              <Badge variant="secondary" className="ml-auto">
                {g.items.length} résultat{g.items.length > 1 ? "s" : ""}
              </Badge>
              {g.tcnCount > 0 && <Badge>{g.tcnCount} TCN</Badge>}
            </div>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 pt-2">
            {g.items.map((p) => (
              <ResultCard key={p.id} result={p} onDelete={onDelete} />
            ))}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
