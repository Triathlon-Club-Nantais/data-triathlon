"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, SegmentedControl, PlaceBadge } from "@/components/tcn";
import { isTCN } from "@/lib/utils/club";
import { StatusBadge } from "@/components/results/StatusBadge";
import { orderParticipations, isNonFinisher } from "@/lib/utils/raceOrder";
import { splitSchema } from "@/lib/utils/splits";
import type { Participation } from "@/lib/types";

// Colonnes fixes (rang, athlète, catég., sexe, temps total) + club en fin.
const BASE_COLS = "54px 1fr 70px 56px 100px";
const CLUB_COL = "1.1fr";

export function RaceFinishers({
  participations,
  tcnCount,
  eventType,
}: {
  participations: Participation[];
  tcnCount: number;
  eventType?: string | null;
}) {
  const router = useRouter();
  const [filter, setFilter] = useState("all");
  const filtered = filter === "tcn" ? participations.filter((p) => isTCN(p.club)) : participations;
  const rows = orderParticipations(filtered);
  const total = participations.length;

  // Colonnes de splits adaptées au sport (clés/libellés alignés sur le backend),
  // limitées aux segments renseignés pour au moins un participant. On se base sur
  // l'ensemble complet (pas les lignes filtrées) pour que les colonnes restent
  // stables quand on bascule le filtre TCN.
  const segments = splitSchema(eventType ?? "").filter((s) =>
    participations.some((p) => p.splits?.[s.key]),
  );
  const fcols = [BASE_COLS, ...segments.map((s) => (s.small ? "64px" : "80px")), CLUB_COL].join(" ");

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 26px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>Finishers</div>
        <SegmentedControl
          tone="ink"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: `Tous les coureurs (${total})` },
            { value: "tcn", label: `Triathlon Club Nantais (${tcnCount})`, dot: true },
          ]}
        />
      </div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: 1080 }}>
          <div style={{ display: "grid", gridTemplateColumns: fcols, gap: "0 12px", padding: "12px 22px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
            <div>Rang</div><div>Athlète</div><div>Catég.</div><div>Sexe</div><div>Temps total</div>
            {segments.map((s) => <div key={s.key}>{s.label}</div>)}
            <div>Club</div>
          </div>
          {rows.map((p) => {
            const own = isTCN(p.club);
            const nf = isNonFinisher(p.status);
            const name = [p.athlete?.nom, p.athlete?.prenom].filter(Boolean).join(" ");
            const splits = p.splits ?? {};
            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                aria-label={`Voir le profil de ${name}`}
                onClick={() => router.push(`/athletes/${p.athlete?.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(`/athletes/${p.athlete?.id}`);
                  }
                }}
                className="tcn-rowlink"
                style={{ display: "grid", gridTemplateColumns: fcols, gap: "0 12px", alignItems: "center", padding: "12px 22px", borderBottom: "1px solid var(--tcn-border-faint)", borderLeft: `3px solid ${own ? "var(--tcn-orange)" : "transparent"}`, background: nf ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)" : undefined }}
              >
                <div>
                  {nf ? (
                    <StatusBadge status={p.status} />
                  ) : p.rank_overall != null ? (
                    <PlaceBadge place={p.rank_overall} style={{ minWidth: 28, fontSize: 16 }} />
                  ) : (
                    <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                  )}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{p.category ?? "—"}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{genderShort(p.athlete?.gender)}</div>
                <div style={{ fontFamily: "var(--tcn-font-cond)", fontWeight: 700, fontSize: 15, color: "var(--tcn-ink)" }}>{p.total_time ?? "—"}</div>
                {segments.map((s) => (
                  <div key={s.key} style={{ fontSize: 13, fontWeight: s.small ? 400 : 600, color: s.small ? "var(--tcn-grey-400)" : "var(--tcn-text-body)" }}>
                    {splits[s.key] ?? "—"}
                  </div>
                ))}
                <div style={{ fontSize: 13, fontWeight: own ? 700 : 400, color: own ? "var(--tcn-orange)" : "var(--tcn-text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.club ?? "—"}</div>
              </div>
            );
          })}
          {rows.length === 0 && <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucun finisher à afficher.</div>}
        </div>
      </div>
      <div style={{ padding: "16px 24px", borderTop: "1px solid var(--tcn-border)", textAlign: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
        {filter === "tcn" ? `${rows.length} athlète${rows.length > 1 ? "s" : ""} TCN affiché${rows.length > 1 ? "s" : ""} · ${total} au total` : `${total} finisher${total > 1 ? "s" : ""} au total`}
      </div>
    </Card>
  );
}

function genderShort(g: string | null | undefined): string {
  if (!g) return "—";
  const c = g.trim().toLowerCase()[0];
  if (c === "f" || c === "w") return "F";
  if (c === "m" || c === "h") return "M";
  return g;
}
