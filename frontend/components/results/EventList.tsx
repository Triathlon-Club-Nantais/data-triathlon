"use client";
import { useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, Badge, FormatChip } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useInfiniteEvents } from "@/lib/queries/events";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import type { EventPage, ParticipationFilters } from "@/lib/types";

const SORT_OPTIONS = [
  { value: "date_desc", label: "Date (récent)" },
  { value: "date_asc", label: "Date (ancien)" },
  { value: "name", label: "Nom" },
];

// Date | Épreuve | Type | Format | Résultats | TCN | →
const COLS = "120px 1fr 150px 90px 110px 90px 28px";

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
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 26px 16px",
        }}
      >
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>
          Toutes les épreuves
        </div>
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

      <div
        style={{
          display: "grid",
          gridTemplateColumns: COLS,
          gap: "0 18px",
          padding: "0 26px 12px",
          fontSize: 12,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: ".04em",
          color: "var(--tcn-text-faint)",
          borderBottom: "1px solid var(--tcn-border)",
        }}
      >
        <div>Date</div>
        <div>Épreuve</div>
        <div>Type</div>
        <div>Format</div>
        <div>Résultats</div>
        <div>TCN</div>
        <div></div>
      </div>

      {events.map((ev) => (
        <Link
          key={ev.id}
          href={`/courses/${ev.id}`}
          className="tcn-rowlink"
          style={{
            display: "grid",
            gridTemplateColumns: COLS,
            gap: "0 18px",
            alignItems: "center",
            padding: "15px 26px",
            borderBottom: "1px solid var(--tcn-border-faint)",
          }}
        >
          <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>
            {formatDate(ev.event_date)}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            <span style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>{ev.event_name}</span>
            {ev.is_relay && <Badge variant="orange">Relais</Badge>}
          </div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(ev.event_type)}</div>
          <div>
            <FormatChip>{formatToken(ev.event_type, ev.distance_km)}</FormatChip>
          </div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>
            {ev.total} résultat{ev.total > 1 ? "s" : ""}
          </div>
          <div>
            {ev.tcn_count > 0 ? (
              <Badge count>{ev.tcn_count}</Badge>
            ) : (
              <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
            )}
          </div>
          <div style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}>→</div>
        </Link>
      ))}

      <div ref={sentinel} aria-hidden />
      {isFetchingNextPage && (
        <p style={{ padding: 16, textAlign: "center", fontSize: 14, color: "var(--tcn-text-faint)" }}>
          Chargement…
        </p>
      )}
    </Card>
  );
}
