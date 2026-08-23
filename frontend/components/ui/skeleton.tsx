import { cn } from "@/lib/utils"

/**
 * Placeholder de chargement.
 *
 * `--tcn-grey-300` et non `bg-muted` : `--muted` vaut `--tcn-fill`, **la même
 * couleur** que `--background` (`--tcn-paper`, `#f4f3f0`). Sur une page, le
 * squelette était donc invisible — ratio 1,00:1 —, et `animate-pulse`
 * n'animant que l'opacité, rien n'apparaissait : un écran vide pendant tout le
 * chargement. Le défaut valait pour les vingt et quelques appelants, il se
 * corrige ici.
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "animate-pulse rounded-md bg-[var(--tcn-grey-300)]",
        className,
      )}
      {...props}
    />
  )
}

export { Skeleton }
