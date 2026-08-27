"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { captureEvent } from "@/lib/posthog";
import type { Season } from "@/lib/types";
import { Badge } from "@/components/tcn";
import { cn } from "@/lib/utils";
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
 *
 * Choisir une saison **remplace** la sélection par défaut (boutons radio) :
 * avant #694, chaque case cochait en plus de la sélection déjà en place, donc
 * choisir une saison passée sans décocher d'abord la saison en cours (cochée
 * par défaut) envoyait les deux au serveur — l'union dominée par la saison en
 * cours donnait l'impression que le choix était ignoré. Le mode comparaison
 * (case « Comparer plusieurs saisons ») rouvre le comportement additif pour
 * qui veut vraiment plusieurs saisons à la fois ; il s'active seul quand
 * l'URL en porte déjà plusieurs.
 */
export function SeasonSelector({ seasons }: { seasons: Season[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const scope = searchParams.get("scope") ?? undefined;
  const seasonsParam = searchParams.get("seasons");
  const [pending, startTransition] = useTransition();
  const selected = useSelectedSeasons();

  // Le mode comparaison suit l'URL par défaut ; `compareOverride` ne porte que
  // le choix explicite de l'utilisateur, et se réinitialise dès que
  // `seasonsParam` change (schéma React « ajuster un état pendant le rendu » —
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes).
  // Une navigation arrière/avant change `seasonsParam` sans démonter le
  // composant, contrairement à un premier rendu : sans cette réinitialisation,
  // `compare` resterait figé sur l'état d'avant la navigation, en désaccord
  // avec la sélection que l'URL affiche désormais — même défaut de source de
  // vérité que #694, à un autre endroit.
  const [prevSeasonsParam, setPrevSeasonsParam] = useState(seasonsParam);
  const [compareOverride, setCompareOverride] = useState<boolean | null>(null);
  if (seasonsParam !== prevSeasonsParam) {
    setPrevSeasonsParam(seasonsParam);
    setCompareOverride(null);
  }
  const compare = compareOverride ?? selected.length > 1;

  function apply(next: number[]) {
    captureEvent("season_changed", { season_count: next.length, seasons: next });
    startTransition(() => router.push(buildSeasonsHref(next, scope, pathname)));
  }

  // Repli sur la première saison retenue, pas sur la saison en cours : quitter
  // le mode comparaison doit garder la saison que l'utilisateur regardait,
  // pas la remplacer par une troisième valeur qu'il n'a pas choisie.
  function toggleCompare(next: boolean) {
    setCompareOverride(next);
    if (!next) apply([selected[0] ?? currentSeason()]);
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
          // Plancher tactile WCAG 2.2 2.5.8 (#479) : un des trois contrôles
          // de la barre d'outils du dashboard mesurés entre 26 et 34 px par
          // l'audit UI/UX.
          minHeight: 28,
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
                  type={compare ? "checkbox" : "radio"}
                  name={compare ? undefined : "season"}
                  checked={checked}
                  onChange={() =>
                    apply(compare ? toggleSeason(selected, s.start_year) : [s.start_year])
                  }
                />
                <span style={{ flex: 1 }}>{s.label}</span>
                <span style={{ color: "var(--tcn-text-faint)", fontSize: 12 }}>
                  {s.event_count}
                </span>
              </label>
            );
          })}
        </div>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "6px 8px",
            borderRadius: 8,
            cursor: "pointer",
            fontSize: 13,
            color: "var(--tcn-text-faint)",
            borderTop: "1px solid var(--tcn-border)",
          }}
        >
          <input
            type="checkbox"
            checked={compare}
            onChange={(e) => toggleCompare(e.target.checked)}
          />
          Comparer plusieurs saisons
        </label>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Ligne des saisons retenues, à placer **sous** l'en-tête, jamais dans la barre
 * d'outils qui porte le déclencheur (#445). Ne rend rien quand une seule saison
 * est sélectionnée : le déclencheur en porte déjà le libellé.
 *
 * L'alignement vient de `className`, jamais d'ici : le déclencheur passe à
 * gauche quand l'en-tête s'empile, et chaque page s'empile à sa propre largeur
 * (`lg` sur /dashboard, `sm` via `PageHeader` sur /club/athletes). Codé en dur,
 * un `justify-end` laissait les tags à droite pendant que le bouton qui les
 * commande était à gauche.
 *
 * `role="group"` porte le nom accessible : détachée du déclencheur, la ligne
 * n'énumérait que des libellés de saison, sans rien pour les relier au bouton
 * — et un `aria-label` sur un `div` nu n'est pas exposé.
 */
export function SeasonTags({ seasons, className }: { seasons: Season[]; className?: string }) {
  const selected = useSelectedSeasons();
  if (selected.length < 2) return null;

  return (
    <div
      data-testid="season-tags"
      role="group"
      aria-label="Saisons retenues"
      className={cn("flex flex-wrap gap-2", className)}
    >
      {selected.map((y) => (
        <Badge key={y} variant="orange">
          {seasons.find((s) => s.start_year === y)?.label ?? `Saison ${y} — ${y + 1}`}
        </Badge>
      ))}
    </div>
  );
}
