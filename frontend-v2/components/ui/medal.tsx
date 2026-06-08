import { cn } from "@/lib/utils";
import { tintedStyle } from "@/lib/sport-colors";

const MEDAL_COLOR: Record<number, string> = {
  1: "var(--gold)",
  2: "var(--silver)",
  3: "var(--bronze)",
};

/**
 * SPLIT — pastille de classement. Or / argent / bronze pour le top 3 (fond
 * teinté 20 %), neutre au-delà. Toujours en mono. Custom (pas d'équivalent shadcn).
 */
export function Medal({
  rank,
  size = 22,
  className,
}: {
  rank: number;
  size?: number;
  className?: string;
}) {
  const color = MEDAL_COLOR[rank] ?? "var(--muted-foreground)";
  return (
    <span
      className={cn("num inline-grid shrink-0 place-content-center font-extrabold", className)}
      style={{
        width: size,
        height: size,
        borderRadius: size,
        fontSize: size * 0.5,
        ...tintedStyle(color),
        // fond teinté 20 % (vs 14 % par défaut) pour les médailles
        background: `color-mix(in oklch, ${color} 20%, transparent)`,
      }}
    >
      {rank}
    </span>
  );
}
