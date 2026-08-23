"use client"

import * as React from "react"
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip"

import { cn } from "@/lib/utils"

/**
 * Infobulle accessible — ouvre au survol **et** au focus clavier (natif au
 * primitif Base UI), ferme sur Échap ou perte de focus. Remplace les `title`
 * natifs du rail replié (#482, NAV-2) : une infobulle native n'ouvre qu'au
 * survol, après ~1 s, jamais au tactile ni au clavier.
 *
 * Délai ramené à 0 ms (`delay` de `TooltipTrigger` vaut 600 ms par défaut) :
 * c'est ce délai-là, pas seulement son absence au clavier, que l'audit
 * reprochait au `title` natif du navigateur.
 */
function Tooltip({ ...props }: TooltipPrimitive.Root.Props) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

function TooltipTrigger({ delay = 0, ...props }: TooltipPrimitive.Trigger.Props) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" delay={delay} {...props} />
}

function TooltipContent({
  className,
  side = "right",
  sideOffset = 8,
  ...props
}: TooltipPrimitive.Popup.Props &
  Pick<TooltipPrimitive.Positioner.Props, "side" | "sideOffset">) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Positioner side={side} sideOffset={sideOffset} className="z-50">
        <TooltipPrimitive.Popup
          data-slot="tooltip-content"
          style={{
            background: "var(--tcn-ink)",
            color: "var(--tcn-paper)",
            borderRadius: "var(--tcn-radius-sm)",
          }}
          className={cn(
            "px-2.5 py-1.5 text-xs font-semibold whitespace-nowrap data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
            className
          )}
          {...props}
        />
      </TooltipPrimitive.Positioner>
    </TooltipPrimitive.Portal>
  )
}

export { Tooltip, TooltipContent, TooltipTrigger }
