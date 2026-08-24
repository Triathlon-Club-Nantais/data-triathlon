import Link from "next/link";
import { Card, FormatChip } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { formatToken } from "@/lib/utils/format";
import type { EventOut } from "@/lib/types";

const GRID_COLUMNS = "88px 1fr auto auto";

/**
 * Les dernières épreuves du club, triées par date décroissante (#483,
 * NAV-7). Remplace l'ancienne carte "Épreuves préférées" (triée par volume
 * de dossards) : la seule liste de l'écran d'atterrissage doit répondre à
 * "qu'est-ce qui vient de se passer", pas à "que fait-on le plus souvent".
 *
 * Reçoit déjà la liste triée et tronquée — `sortEventsByDateDesc` vit dans
 * `lib/utils/event.ts`, appelé côté page (`dashboard/page.tsx`). Ce
 * composant ne fait que rendre, dans l'ordre reçu.
 */
export function RecentCourses({ events }: { events: EventOut[] }) {
  return (
    <Card>
      <h2
        style={{
          fontFamily: "var(--tcn-font-display)",
          fontSize: 24,
          fontWeight: 400,
          color: "var(--tcn-ink)",
          margin: 0,
          marginBottom: 18,
        }}
      >
        Dernières épreuves
      </h2>
      {events.length === 0 ? (
        <EmptyState
          bare
          className="py-6"
          title="Aucune épreuve récente à afficher"
          action={
            <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
              Ajouter une épreuve →
            </Link>
          }
        />
      ) : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: GRID_COLUMNS,
              gap: "0 14px",
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: ".04em",
              color: "var(--tcn-text-faint)",
              paddingBottom: 10,
              borderBottom: "1px solid var(--tcn-border)",
            }}
          >
            <div>Date</div>
            <div>Épreuve</div>
            <div>Format</div>
            <div style={{ textAlign: "right" }}>Dossards</div>
          </div>
          {events.map((e, i) => (
            // prefetch={false} (#425) : jusqu'à 6 liens au-dessus de la ligne
            // de flottaison, next/link les prefetch tous par défaut dès
            // l'atterrissage sur /dashboard — un coût réseau pour des
            // épreuves au hasard, rarement celle que le visiteur ouvrira.
            <Link
              key={e.id}
              href={`/courses/${e.id}`}
              prefetch={false}
              className="tcn-rowlink"
              style={{
                display: "grid",
                gridTemplateColumns: GRID_COLUMNS,
                gap: "0 14px",
                alignItems: "center",
                padding: "12px 0",
                borderBottom: i < events.length - 1 ? "1px solid var(--tcn-border-faint)" : "none",
                fontSize: 15,
              }}
            >
              <span style={{ fontFamily: "var(--tcn-font-display)", color: "var(--tcn-text-muted)" }}>
                {formatDate(e.event_date) || "—"}
              </span>
              <span style={{ color: "var(--tcn-ink)", fontWeight: 600 }}>
                {formatEventName(e.event_name, e.is_relay)}
              </span>
              <FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>
              <b style={{ textAlign: "right", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>
                {e.total}
              </b>
            </Link>
          ))}
        </>
      )}
    </Card>
  );
}
