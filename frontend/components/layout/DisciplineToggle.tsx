"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";

import { SPORTS_ALL, SPORTS_PARAM } from "@/lib/scope";
import { RANK_PARAM } from "@/lib/rank";

/**
 * Ouvre les compteurs aux disciplines hors fédération triathlon.
 *
 * Par défaut, trail, course à pied et cyclisme sont exclus des compteurs du
 * club : ils restent consultables ailleurs, mais ne se lisent pas comme des
 * résultats de triathlon (issue #76).
 */
export function DisciplineToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();
  const toutesDisciplines = sp.get(SPORTS_PARAM) === SPORTS_ALL;

  function basculer(toutes: boolean) {
    // `router.push` est un vrai aller-retour serveur (contrairement à
    // `RankTypeToggle`, #328) : ne cloner que les paramètres que le rendu
    // serveur lit réellement. `?rank=` est strictement client (#425) — le
    // propager déclenche un fetch RSC pour une valeur que le serveur ignore.
    const params = new URLSearchParams(sp.toString());
    params.delete(RANK_PARAM);
    if (toutes) params.set(SPORTS_PARAM, SPORTS_ALL);
    else params.delete(SPORTS_PARAM);
    const qs = params.toString();
    startTransition(() => router.push(`${pathname}${qs ? `?${qs}` : ""}`));
  }

  return (
    <label
      data-pending={pending || undefined}
      className="inline-flex cursor-pointer items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-xs font-semibold text-[var(--tcn-text-faint)] data-pending:opacity-70"
    >
      <input
        type="checkbox"
        checked={toutesDisciplines}
        onChange={(e) => basculer(e.target.checked)}
        className="size-3.5 accent-[var(--tcn-orange)]"
      />
      Inclure les autres disciplines
    </label>
  );
}
