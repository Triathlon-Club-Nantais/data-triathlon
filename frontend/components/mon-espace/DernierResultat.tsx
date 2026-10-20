import Link from "next/link";
import { Badge, Card, Eyebrow } from "@/components/tcn";
import { ResultCardDownload } from "@/components/participations/ResultCardDownload";
import type { Participation } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { ordinalFr } from "@/lib/utils/format";

/** Dernier résultat validé de la sélection (#1700). */
export function DernierResultat({ participation, record }: { participation: Participation | null; record: boolean }) {
  return (
    <Card padding={20}>
      <Eyebrow>Mon dernier résultat</Eyebrow>
      {participation === null ? (
        <>
          <p style={{ margin: "12px 0 0", fontSize: 14, color: "var(--tcn-text-muted)" }}>Aucun résultat sur cette sélection.</p>
          <p style={{ margin: "6px 0 0", fontSize: 14, color: "var(--tcn-text-muted)" }}>
            Changez de saison ou{" "}
            <Link href="/ajouter" className="font-semibold text-accent-ink underline underline-offset-2">
              ajoutez une épreuve
            </Link>
            .
          </p>
        </>
      ) : (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          <Link
            href={`/courses/${participation.course.id}/participations/${participation.id}`}
            className="tcn-cible-tactile underline underline-offset-2"
            style={{ fontSize: 16, fontWeight: 600 }}
          >
            {participation.course.name}
          </Link>
          <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>{formatDate(participation.course.event_date)}</span>
          <span style={{ fontFamily: "var(--tcn-font-display)", fontSize: 26, color: "var(--tcn-ink)" }}>{participation.total_time}</span>
          {participation.rank_overall != null && <span style={{ fontSize: 14 }}>{ordinalFr(participation.rank_overall)} au général</span>}
          {record && (
            <div>
              <Badge variant="orange">record perso</Badge>
            </div>
          )}
          <ResultCardDownload participation={participation} libelle="Ma carte résultat" />
        </div>
      )}
    </Card>
  );
}
