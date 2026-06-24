"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, SegmentedControl, PlaceBadge } from "@/components/tcn";
import { isTCN } from "@/lib/utils/club";
import type { Participation } from "@/lib/types";

const FCOLS = "54px 1fr 70px 56px 100px 80px 64px 80px 64px 80px 1.1fr";
const SPLIT_KEYS: [keyof NonNullable<Participation["splits"]>, string][] = [
  ["swim", "Natation"],
  ["t1", "T1"],
  ["bike", "Vélo"],
  ["t2", "T2"],
  ["run", "Course"],
];

export function RaceFinishers({
  participations,
  tcnCount,
}: {
  participations: Participation[];
  tcnCount: number;
}) {
  const router = useRouter();
  const [filter, setFilter] = useState("all");
  const rows = filter === "tcn" ? participations.filter((p) => isTCN(p.club)) : participations;
  const total = participations.length;

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
          <div style={{ display: "grid", gridTemplateColumns: FCOLS, gap: "0 12px", padding: "12px 22px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
            <div>Rang</div><div>Athlète</div><div>Catég.</div><div>Sexe</div><div>Temps total</div>
            {SPLIT_KEYS.map(([, label]) => <div key={label}>{label}</div>)}
            <div>Club</div>
          </div>
          {rows.map((p) => {
            const own = isTCN(p.club);
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
                style={{ display: "grid", gridTemplateColumns: FCOLS, gap: "0 12px", alignItems: "center", padding: "12px 22px", borderBottom: "1px solid var(--tcn-border-faint)", borderLeft: `3px solid ${own ? "var(--tcn-orange)" : "transparent"}` }}
              >
                <div>{p.rank_overall != null ? <PlaceBadge place={p.rank_overall} style={{ minWidth: 28, fontSize: 16 }} /> : <span style={{ color: "var(--tcn-text-faint)" }}>—</span>}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{p.category ?? "—"}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{genderShort(p.athlete?.gender)}</div>
                <div style={{ fontFamily: "var(--tcn-font-cond)", fontWeight: 700, fontSize: 15, color: "var(--tcn-ink)" }}>{p.total_time ?? "—"}</div>
                {SPLIT_KEYS.map(([key]) => {
                  const isTrans = key === "t1" || key === "t2";
                  return (
                    <div key={key} style={{ fontSize: 13, fontWeight: isTrans ? 400 : 600, color: isTrans ? "var(--tcn-grey-400)" : "var(--tcn-text-body)" }}>
                      {splits[key] ?? "—"}
                    </div>
                  );
                })}
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
