// Pas de `"use client"` ici : ce module n'est importé que par `AppNav`, qui
// porte la directive. L'ajouter en ferait un **point d'entrée** client, dont
// Next exige des props sérialisables — or ce composant prend deux callbacks.
import { useEffect, useState } from "react";
import { Avatar, Input, Modal } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import type { AthleteBrief } from "@/lib/types";

/** Athlète retenu en session, mémorisé d'une visite à l'autre. */
export type PickedAthlete = { id: number; name: string };

const STORE = "tcn-athlete";

/**
 * Le stock est éditable par l'utilisateur : une valeur JSON-valide mais de
 * mauvaise forme ferait planter l'affichage (`name.split`) ou router vers
 * `/athletes/undefined`. On la traite comme une absence de choix.
 */
export function readAthlete(): PickedAthlete | null {
  try {
    const valeur: unknown = JSON.parse(window.localStorage.getItem(STORE) ?? "null");
    const candidat = valeur as PickedAthlete | null;
    return typeof candidat?.id === "number" && typeof candidat?.name === "string" ? candidat : null;
  } catch {
    return null;
  }
}

export function writeAthlete(a: PickedAthlete) {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(a));
  } catch {
    /* mode privé, quota : le choix vaut alors pour la session en cours seule. */
  }
}

type AthleteRow = AthleteBrief & { count: number };

/**
 * Recherche d'un athlète du club. Interroge l'API à partir de **2 caractères**,
 * après 250 ms de silence, et plafonne à 12 résultats.
 */
export function AthletePicker({
  onClose,
  onPick,
}: {
  onClose: () => void;
  onPick: (athlete: PickedAthlete) => void;
}) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<AthleteRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRows([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const parts = await apiClient.listParticipations({ name: q, page_size: 100 });
        if (cancelled) return;
        const byAthlete = new Map<number, AthleteRow>();
        for (const p of parts) {
          const a = p.athlete;
          const existing = byAthlete.get(a.id);
          if (existing) existing.count += 1;
          else byAthlete.set(a.id, { ...a, count: 1 });
        }
        setRows([...byAthlete.values()].sort((x, y) => y.count - x.count).slice(0, 12));
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query]);

  return (
    <Modal
      eyebrow="Accès athlète"
      title="Sélectionne ton nom"
      onClose={onClose}
      width={520}
      footer={
        <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", textAlign: "center" }}>
          Pas de blocage d&apos;accès — choisis librement ton profil.
        </div>
      }
    >
      <Input
        icon={<span>⌕</span>}
        value={query}
        autoFocus
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher un nom…"
      />
      <div style={{ marginTop: 8 }}>
        {rows.map((a) => {
          const fullName = [a.prenom, a.nom].filter(Boolean).join(" ");
          return (
            <div
              key={a.id}
              role="button"
              tabIndex={0}
              aria-label={`Choisir ${fullName}`}
              onClick={() => onPick({ id: a.id, name: fullName })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPick({ id: a.id, name: fullName });
                }
              }}
              style={{ display: "flex", alignItems: "center", gap: 14, padding: "11px 14px", borderRadius: 12, cursor: "pointer" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--tcn-fill)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              onFocus={(e) => (e.currentTarget.style.background = "var(--tcn-fill)")}
              onBlur={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <Avatar name={fullName} size={40} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, color: "var(--tcn-ink)", fontSize: 15 }}>{fullName}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
                  {a.club ?? "Sans club"} · {a.count} course{a.count > 1 ? "s" : ""}
                </div>
              </div>
              <span style={{ color: "var(--tcn-text-disabled)", fontSize: 18 }}>→</span>
            </div>
          );
        })}
        {query.trim().length >= 2 && !loading && rows.length === 0 && (
          <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucun athlète trouvé.</div>
        )}
        {query.trim().length < 2 && (
          <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Saisis au moins 2 lettres de ton nom.
          </div>
        )}
      </div>
    </Modal>
  );
}
