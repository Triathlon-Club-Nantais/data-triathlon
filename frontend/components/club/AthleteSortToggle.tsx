"use client";
import { usePathname, useSearchParams } from "next/navigation";

/** Nom du paramètre d'URL pilotant le tri de la liste des athlètes (#274). */
export const SORT_PARAM = "sort";

/** Nombre d'épreuves décroissant, comportement le plus utile par défaut. */
export type AthleteSortType = "count" | "nom";
export const SORT_DEFAULT: AthleteSortType = "count";

const CANONICAL: readonly AthleteSortType[] = ["count", "nom"];

/** Whitelist stricte : toute valeur hors des deux tris connus retombe sur le défaut. */
export function sortTypeFromParam(v: string | undefined): AthleteSortType {
  return (CANONICAL as readonly string[]).includes(v ?? "") ? (v as AthleteSortType) : SORT_DEFAULT;
}

const OPTIONS: { value: AthleteSortType; label: string }[] = [
  { value: "count", label: "Nombre d'épreuves" },
  { value: "nom", label: "Nom de famille" },
];

/**
 * Bascule de tri — même mécanique que `RankTypeToggle` (#328) : `?sort=`
 * n'est lu par aucun rendu serveur (`AthleteSeasonList` a déjà toute la liste
 * en mémoire), donc `pushState` + recalcul client plutôt qu'un aller-retour
 * réseau pour re-trier une liste déjà chargée.
 */
export function AthleteSortToggle() {
  const pathname = usePathname();
  const sp = useSearchParams();
  const active = sortTypeFromParam(sp.get(SORT_PARAM) ?? undefined);

  function apply(next: AthleteSortType) {
    const params = new URLSearchParams(sp.toString());
    if (next === SORT_DEFAULT) params.delete(SORT_PARAM);
    else params.set(SORT_PARAM, next);
    const qs = params.toString();
    window.history.pushState(null, "", `${pathname}${qs ? `?${qs}` : ""}`);
  }

  return (
    <div
      role="radiogroup"
      aria-label="Trier par"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0,
        padding: 3,
        borderRadius: 10,
        border: "1px solid var(--tcn-border)",
        background: "var(--tcn-surface, #fff)",
      }}
    >
      {OPTIONS.map(({ value, label }) => {
        const checked = value === active;
        return (
          <label
            key={value}
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "6px 12px",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 700,
              color: checked ? "var(--tcn-ink)" : "var(--tcn-text-muted)",
              background: checked ? "var(--tcn-fill)" : "transparent",
              transition: "background 120ms, color 120ms",
            }}
          >
            <input
              type="radio"
              name="athlete-sort"
              value={value}
              checked={checked}
              onChange={() => apply(value)}
              style={{ position: "absolute", opacity: 0, pointerEvents: "none" }}
              aria-label={label}
            />
            {label}
          </label>
        );
      })}
    </div>
  );
}
