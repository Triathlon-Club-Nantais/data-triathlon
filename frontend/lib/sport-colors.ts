// Échelle catégorielle des disciplines (TCN Design System — l'en-tête nommait
// encore « SPLIT », le design system qu'il a remplacé). Renvoie un token CSS (`var(--…)`)
// pour colorer tags, avatars, segments de splits et data-viz de façon cohérente.

/** Couleur fixe d'une discipline (référence une variable de `globals.css`). */
const DISCIPLINE_COLORS = {
  swim: "var(--swim)",
  bike: "var(--bike)",
  run: "var(--run)",
  violet: "var(--violet)",
  // Triathlon = orange de marque TCN (--tri), découplé du primaire (bleu nuit).
  accent: "var(--tri)",
} as const;

/** Couleur associée à une famille de type d'épreuve. */
export function eventTypeColor(type: string | null | undefined): string {
  const t = (type ?? "").toLowerCase();
  if (t.startsWith("triathlon")) return DISCIPLINE_COLORS.accent;
  if (t.startsWith("duathlon") || t === "bike-run" || t.startsWith("cyclisme"))
    return DISCIPLINE_COLORS.bike;
  if (t.startsWith("swimrun") || t === "aquathlon" || t === "aquarun")
    return DISCIPLINE_COLORS.swim;
  if (t.startsWith("trail") || t.startsWith("course-a-pied"))
    return DISCIPLINE_COLORS.run;
  return "var(--muted-foreground)";
}

/**
 * Règle d'or : **aplat = couleur pleine, texte = `…-ink`**.
 * Fond teinté à 14 %, libellé mixé vers `--foreground` de `--ink-mix`.
 */
export function tintedStyle(color: string): React.CSSProperties {
  return {
    color: `color-mix(in oklch, ${color}, var(--foreground) var(--ink-mix))`,
    background: `color-mix(in oklch, ${color} 14%, transparent)`,
  };
}
