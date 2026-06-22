import { cn } from "@/lib/utils";
import { avatarColor, tintedStyle } from "@/lib/sport-colors";

/**
 * SPLIT — avatar à initiales. Couleur de fond hashée sur le nom (échelle
 * catégorielle), initiales en mono. Fond teinté 18 %, libellé mixé `…-ink`.
 */
export function InitialsAvatar({
  name,
  size = 34,
  className,
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const initials =
    name
      .split(" ")
      .map((w) => w[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "—";
  const color = avatarColor(name);
  return (
    <div
      className={cn("num grid shrink-0 place-content-center font-extrabold tracking-[0.02em]", className)}
      style={{
        width: size,
        height: size,
        borderRadius: size,
        fontSize: size * 0.38,
        ...tintedStyle(color),
        background: `color-mix(in oklch, ${color} 18%, transparent)`,
      }}
      aria-hidden
    >
      {initials}
    </div>
  );
}
