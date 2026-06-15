"use client";
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SportBadge } from "./SportBadge";
import { EventParticipations } from "./EventParticipations";
import { useInfiniteEvents } from "@/lib/queries/events";
import { useDeleteParticipation } from "@/lib/queries/participations";
import { formatDate } from "@/lib/utils/date";
import type { EventPage, ParticipationFilters } from "@/lib/types";

const SORT_OPTIONS = [
  { value: "date_desc", label: "Date (récent)" },
  { value: "date_asc", label: "Date (ancien)" },
  { value: "name", label: "Nom" },
];

export function EventList({
  filters,
  initial,
}: {
  filters: ParticipationFilters;
  initial?: EventPage;
}) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteEvents(
    filters,
    initial,
  );
  const qc = useQueryClient();
  const del = useDeleteParticipation();
  const router = useRouter();
  const sp = useSearchParams();
  const sentinel = useRef<HTMLDivElement | null>(null);

  const events = data?.pages.flatMap((p) => p.items) ?? [];

  // Scroll infini : charge la page suivante quand la sentinelle entre dans le viewport.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && !isFetchingNextPage) fetchNextPage();
    });
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  async function onDelete(id: number) {
    try {
      await del.mutateAsync(id);
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["course-participations"] });
      router.refresh(); // rafraîchit les compteurs rendus côté serveur
      toast.success("Résultat supprimé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  function setSort(value: string) {
    const params = new URLSearchParams(sp.toString());
    params.set("sort", value);
    router.push(`/resultats?${params.toString()}`);
  }

  const currentSort = sp.get("sort") ?? "date_desc";

  if (!isLoading && events.length === 0) {
    return (
      <EmptyState
        title="Aucun résultat"
        description="Importez une épreuve depuis une URL de chronométrage pour voir apparaître les résultats ici."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Select value={currentSort} onValueChange={(v) => setSort(v as string)}>
          <SelectTrigger className="h-9 w-44">
            <SelectValue>
              {(v) => SORT_OPTIONS.find((o) => o.value === v)?.label ?? "Trier"}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Accordion multiple className="space-y-2">
        {events.map((ev) => (
          <AccordionItem key={ev.id} value={String(ev.id)} className="rounded-md border px-4">
            <AccordionTrigger>
              <div className="flex flex-1 flex-wrap items-center gap-3 pr-4 text-left">
                <span className="font-semibold">{ev.event_name}</span>
                <SportBadge type={ev.event_type} />
                {ev.event_date && (
                  <span className="text-sm text-muted-foreground">{formatDate(ev.event_date)}</span>
                )}
                {ev.is_relay && <Badge variant="destructive">Relais</Badge>}
                <Badge variant="secondary" className="ml-auto">
                  {ev.total} résultat{ev.total > 1 ? "s" : ""}
                </Badge>
                {ev.tcn_count > 0 && <Badge>{ev.tcn_count} TCN</Badge>}
              </div>
            </AccordionTrigger>
            <AccordionContent className="space-y-3 pt-2">
              <EventParticipations
                courseId={ev.id}
                club={filters.club}
                name={filters.name}
                onDelete={onDelete}
              />
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>

      <div ref={sentinel} aria-hidden />
      {isFetchingNextPage && (
        <p className="py-4 text-center text-sm text-muted-foreground">Chargement…</p>
      )}
    </div>
  );
}
