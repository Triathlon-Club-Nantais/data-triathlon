"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { captureEvent } from "@/lib/posthog";
import type { Season } from "@/lib/types";
import { Badge } from "@/components/tcn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  currentSeason,
  parseSeasonsParam,
  seasonSelectionLabel,
  serializeSeasons,
  toggleSeason,
} from "@/lib/utils/season";

/**
 * Construit l'URL `pathname` reflétant la sélection de saisons.
 * Le paramètre `seasons` est omis quand la sélection est vide ou égale à la
 * seule saison en cours (retour implicite au défaut). `scope` est préservé.
 *
 * `pathname` est un paramètre explicite (pas de défaut) plutôt qu'une valeur
 * codée en dur : le composant sert `/dashboard` **et** `/club/athletes`
 * (#274), deux pages qui lisent `?seasons=` côté serveur.
 */
export function buildSeasonsHref(
  selected: number[],
  scope: string | undefined,
  pathname: string,
): string {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  const isDefault = selected.length === 0 || (selected.length === 1 && selected[0] === currentSeason());
  if (!isDefault) params.set("seasons", serializeSeasons(selected));
  const qs = params.toString();
  return `${pathname}${qs ? `?${qs}` : ""}`;
}

export function SeasonSelector({ seasons }: { seasons: Season[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const scope = sp.get("scope") ?? undefined;
  const [pending, startTransition] = useTransition();

  const fromUrl = parseSeasonsParam(sp.get("seasons"));
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];

  function apply(next: number[]) {
    captureEvent("season_changed", { season_count: next.length, seasons: next });
    startTransition(() => router.push(buildSeasonsHref(next, scope, pathname)));
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <Popover>
        <PopoverTrigger
          aria-label="Choisir les saisons"
          data-pending={pending || undefined}
          className="data-pending:opacity-70"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            borderRadius: 10,
            border: "1px solid var(--tcn-border)",
            background: "var(--tcn-surface, #fff)",
            color: "var(--tcn-ink)",
            fontWeight: 700,
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          {seasonSelectionLabel(selected)}
        </PopoverTrigger>
        <PopoverContent
          align="end"
          data-pending={pending || undefined}
          className="data-pending:opacity-70"
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {seasons.map((s) => {
              const checked = selected.includes(s.start_year);
              return (
                <label
                  key={s.start_year}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "6px 8px",
                    borderRadius: 8,
                    cursor: "pointer",
                    fontSize: 14,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => apply(toggleSeason(selected, s.start_year))}
                  />
                  <span style={{ flex: 1 }}>{s.label}</span>
                  <span style={{ color: "var(--tcn-text-faint)", fontSize: 12 }}>
                    {s.event_count}
                  </span>
                </label>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>

      {selected.length > 1 &&
        selected.map((y) => (
          <Badge key={y} variant="orange">
            {seasons.find((s) => s.start_year === y)?.label ?? `Saison ${y} — ${y + 1}`}
          </Badge>
        ))}
    </div>
  );
}
