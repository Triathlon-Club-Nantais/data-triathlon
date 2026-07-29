"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";

import { RANK_DEFAULT, RANK_PARAM, rankTypeFromParam, type RankType } from "@/lib/rank";

const OPTIONS: readonly { value: RankType; label: string }[] = [
  { value: "scratch", label: "Scratch" },
  { value: "category", label: "Catégorie" },
  { value: "gender", label: "Genre" },
  { value: "all", label: "Tous" },
];

/**
 * Sélecteur de type de rang (#104). Radio-group horizontal, mono-choix,
 * URL-persistant : le choix vit dans `?rank=…`, jamais en localStorage.
 * Le défaut (scratch) est représenté par l'absence du paramètre — on nettoie
 * l'URL quand l'utilisateur revient dessus pour éviter deux liens différents
 * pour une même vue.
 */
export function RankTypeToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();
  const active = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);

  function apply(next: RankType) {
    const params = new URLSearchParams(sp.toString());
    if (next === RANK_DEFAULT) params.delete(RANK_PARAM);
    else params.set(RANK_PARAM, next);
    const qs = params.toString();
    startTransition(() => router.push(`${pathname}${qs ? `?${qs}` : ""}`));
  }

  return (
    <div
      role="radiogroup"
      aria-label="Type de rang"
      data-pending={pending || undefined}
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
      {OPTIONS.map((opt) => {
        const checked = opt.value === active;
        return (
          <label
            key={opt.value}
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
              name="rank-type"
              value={opt.value}
              checked={checked}
              onChange={() => apply(opt.value)}
              style={{ position: "absolute", opacity: 0, pointerEvents: "none" }}
              aria-label={opt.label}
            />
            {opt.label}
          </label>
        );
      })}
    </div>
  );
}
