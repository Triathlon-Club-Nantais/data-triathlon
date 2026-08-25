"use client";

import { useState } from "react";
import { Card } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import type { Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";

/** File des résultats en attente de validation (#271, US1), avec un second
 *  onglet pour les entrées signalées non conformes (#437) — tous clubs
 *  confondus. */
export function ValidationQueue({
  participations,
  rejected = [],
  selectedId,
  onSelect,
  traitees = 0,
}: {
  participations: Participation[];
  rejected?: Participation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  /** Entrées traitées depuis l'ouverture de l'écran (#490, PROF-9). Non
   *  persisté : c'est un encouragement, pas une donnée. */
  traitees?: number;
}) {
  const [onglet, setOnglet] = useState<"file" | "non-conformes">("file");
  const liste = onglet === "file" ? participations : rejected;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8 }}>
        {/* `minHeight: 28`, `padding` : plancher tactile WCAG 2.2 2.5.8, contre
            ~20 px sans padding avant #479. */}
        <button
          type="button"
          onClick={() => setOnglet("file")}
          aria-pressed={onglet === "file"}
          style={{ fontWeight: onglet === "file" ? 700 : 400, background: "none", border: "none", cursor: "pointer", padding: "6px 4px", minHeight: 28, display: "inline-flex", alignItems: "center" }}
        >
          File ({participations.length})
        </button>
        <button
          type="button"
          onClick={() => setOnglet("non-conformes")}
          aria-pressed={onglet === "non-conformes"}
          style={{ fontWeight: onglet === "non-conformes" ? 700 : 400, background: "none", border: "none", cursor: "pointer", padding: "6px 4px", minHeight: 28, display: "inline-flex", alignItems: "center" }}
        >
          Non conformes ({rejected.length})
        </button>
        {traitees > 0 && (
          <span style={{ marginLeft: "auto", alignSelf: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
            {traitees} traité{traitees > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {liste.length === 0 ? (
        <Card padding={24}>
          <EmptyState
            bare
            title={onglet === "file" ? "File vide, merci !" : "Aucun résultat signalé non conforme"}
            description={
              onglet === "file" ? "Tous les résultats déclarés ont été relus." : undefined
            }
          />
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {liste.map((participation) => {
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
      )}
    </div>
  );
}
