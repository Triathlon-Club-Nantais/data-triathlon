"use client";
import type { TrainingGroup } from "@/lib/types";

/**
 * Choix multiple des groupes visés (#1291) : cases natives dans un `fieldset`,
 * patron de `PermissionGrid`, utilisables au doigt à 375 px.
 */
export function GroupesPicker({
  groupes,
  value,
  onChange,
}: {
  groupes: TrainingGroup[];
  value: number[];
  onChange: (ids: number[]) => void;
}) {
  if (groupes.length === 0) return null;
  const choisis = new Set(value);
  return (
    <fieldset className="space-y-1.5">
      <legend className="text-sm font-medium">Groupes visés</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {groupes.map((groupe) => (
          <label key={groupe.id} className="flex min-h-9 items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--tcn-orange)]"
              checked={choisis.has(groupe.id)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...value, groupe.id].sort((a, b) => a - b)
                    : value.filter((id) => id !== groupe.id),
                )
              }
            />
            {groupe.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
