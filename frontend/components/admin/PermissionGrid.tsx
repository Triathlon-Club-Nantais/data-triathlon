"use client";
import { Label } from "@/components/ui/label";
import type { PermissionGroup } from "@/lib/types";

/**
 * Les pouvoirs à cocher, **groupés par fonctionnalité**.
 *
 * Le regroupement vient du serveur (`GET /admin/permissions`) et n'est ni
 * retrié ni ré-aplati ici : composer un rôle en cochant dans une liste plate de
 * dix-huit codes techniques est précisément le geste que cet écran existe pour
 * éviter. Le refaire côté front créerait un second endroit où cet ordre se
 * décide.
 *
 * `<fieldset>`/`<legend>` plutôt qu'une `<div>` stylée : le regroupement est
 * **sémantique** avant d'être visuel, et seul le premier annonce à un lecteur
 * d'écran que les cases qui suivent forment un ensemble nommé.
 *
 * Sans `onToggle`, la grille est en lecture seule — c'est ce qui sert l'écran
 * de consultation et le panneau d'un rôle superutilisateur, dont la composition
 * enregistrée reste affichée mais inerte.
 */
export function PermissionGrid({
  groupes,
  coches,
  onToggle,
  disabledCodes,
  raison,
  idPrefixe,
}: {
  groupes: PermissionGroup[];
  coches: ReadonlySet<string>;
  onToggle?: (code: string, coche: boolean) => void;
  /** Codes que l'utilisateur connecté ne porte pas : figés dans leur état. */
  disabledCodes?: ReadonlySet<string>;
  /** Pourquoi ces codes sont figés. Rendue en texte, pas seulement en `title`. */
  raison?: string;
  /**
   * Préfixe des `id`. Deux grilles coexistent dès qu'on ouvre la création
   * par-dessus un panneau déplié : sans lui, elles porteraient les mêmes `id` de
   * case, et une étiquette désignerait la case de l'autre grille.
   */
  idPrefixe: string;
}) {
  const idRaison = `${idPrefixe}-raison`;

  return (
    <div className="space-y-6">
      {groupes.map((groupe) => (
        <fieldset key={groupe.feature} className="space-y-3">
          <legend className="mb-2 text-sm font-semibold text-accent-ink">
            {groupe.feature}
          </legend>
          {groupe.permissions.map((pouvoir) => {
            const id = `${idPrefixe}-${pouvoir.code}`;
            const idDescription = `${id}-description`;
            const fige = !onToggle || (disabledCodes?.has(pouvoir.code) ?? false);
            const figeParDroit = Boolean(onToggle) && fige;

            return (
              <div key={pouvoir.code} className="flex items-start gap-2.5">
                <input
                  id={id}
                  type="checkbox"
                  className="mt-1"
                  checked={coches.has(pouvoir.code)}
                  disabled={fige}
                  aria-describedby={
                    figeParDroit && raison
                      ? `${idDescription} ${idRaison}`
                      : idDescription
                  }
                  onChange={(e) => onToggle?.(pouvoir.code, e.target.checked)}
                />
                <div className="space-y-0.5">
                  <Label htmlFor={id} className="font-medium">
                    {pouvoir.label}
                  </Label>
                  <p id={idDescription} className="text-sm text-muted-foreground">
                    {pouvoir.description}
                  </p>
                </div>
              </div>
            );
          })}
        </fieldset>
      ))}

      {raison && disabledCodes && disabledCodes.size > 0 && onToggle && (
        <p id={idRaison} className="text-sm text-muted-foreground">
          {raison}
        </p>
      )}
    </div>
  );
}
