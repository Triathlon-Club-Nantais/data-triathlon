import { Card } from "@/components/tcn";
import type { Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";

/** File des résultats en attente de validation (#271, US1) — tous clubs confondus. */
export function ValidationQueue({
  participations,
  selectedId,
  onSelect,
}: {
  participations: Participation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  if (participations.length === 0) {
    return (
      <Card padding={24}>
        <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, textAlign: "center" }}>
          Aucun résultat en attente de validation.
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {participations.map((participation) => {
        const selectionnee = participation.id === selectedId;
        return (
          <button
            key={participation.id}
            type="button"
            className="tcn-rowlink"
            aria-current={selectionnee ? "true" : undefined}
            onClick={() => onSelect(participation.id)}
            style={{
              textAlign: "left",
              padding: "14px 16px",
              borderRadius: "var(--tcn-radius-lg)",
              border: `1.5px solid ${selectionnee ? "var(--tcn-orange)" : "var(--tcn-border)"}`,
              background: selectionnee ? "var(--tcn-orange-08)" : "var(--tcn-surface)",
              display: "flex",
              flexDirection: "column",
              gap: 4,
              width: "100%",
            }}
          >
            <span style={{ fontWeight: 700, color: "var(--tcn-ink)" }}>
              {participation.athlete.prenom} {participation.athlete.nom}
            </span>
            <span style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
              {formatEventName(participation.course.name, participation.course.is_relay)}
            </span>
            {participation.team_name && (
              <span style={{ fontSize: 12, color: "var(--tcn-text-body)" }}>
                Équipe : <strong>{participation.team_name}</strong>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
