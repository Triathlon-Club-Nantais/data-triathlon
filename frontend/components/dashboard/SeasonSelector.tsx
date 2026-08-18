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

/** Sélection courante, lue dans l'URL, avec repli sur la saison en cours. */
function useSelectedSeasons(): number[] {
  const fromUrl = parseSeasonsParam(useSearchParams().get("seasons"));
  return fromUrl.length > 0 ? fromUrl : [currentSeason()];
}

/**
 * Déclencheur seul — un bouton, rien autour (#445).
 *
 * Les saisons retenues **ne sont pas rendues ici** : elles vivent dans
 * `SeasonTags`, que l'appelant place hors de sa barre d'outils. Rendues à côté
 * du déclencheur, elles élargissaient la barre au point de la faire passer
 * sous le titre, tout à gauche — les boutons de sélection changeaient donc de
 * place à la deuxième saison cochée.
 */
export function SeasonSelector({ seasons }: { seasons: Season[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const scope = useSearchParams().get("scope") ?? undefined;
  const [pending, startTransition] = useTransition();
  const selected = useSelectedSeasons();

  function apply(next: number[]) {
    captureEvent("season_changed", { season_count: next.length, seasons: next });
    startTransition(() => router.push(buildSeasonsHref(next, scope, pathname)));
  }

  return (
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
  );
}

/**
 * Ligne des saisons retenues, à placer **hors de la barre d'outils** qui porte
 * le déclencheur — sous l'en-tête (#445). Ne rend rien quand une seule saison
 * est sélectionnée : le déclencheur en porte déjà le libellé.
 *
 * `width:0` + `minWidth:100%` réclame une ligne entière sans peser sur la
 * largeur intrinsèque du parent : dans un conteneur `flex-wrap` la ligne
 * s'isole sans l'élargir, dans un conteneur en flux normal elle occupe
 * simplement toute la largeur. Un `flexBasis:"100%"` provoquerait bien le
 * retour à la ligne, mais compterait dans le `max-content` du parent.
 */
export function SeasonTags({ seasons }: { seasons: Season[] }) {
  const selected = useSelectedSeasons();
  if (selected.length < 2) return null;

  return (
    <div
      data-testid="season-tags"
      style={{
        width: 0,
        minWidth: "100%",
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "flex-end",
        gap: 8,
      }}
    >
      {selected.map((y) => (
        <Badge key={y} variant="orange">
          {seasons.find((s) => s.start_year === y)?.label ?? `Saison ${y} — ${y + 1}`}
        </Badge>
      ))}
    </div>
  );
}
