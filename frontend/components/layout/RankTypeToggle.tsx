"use client";
import { useSearchParams, usePathname } from "next/navigation";

import { RANK_DEFAULT, RANK_PARAM, rankTypeFromParam, type RankType } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import { SegmentedControl } from "@/components/tcn/SegmentedControl";

const OPTION_VALUES: readonly RankType[] = ["scratch", "category", "gender", "all"];

/**
 * Sélecteur de type de rang (#104). Radio-group horizontal, mono-choix,
 * URL-persistant : le choix vit dans `?rank=…`, jamais en localStorage.
 * Le défaut (scratch) est représenté par l'absence du paramètre — on nettoie
 * l'URL quand l'utilisateur revient dessus pour éviter deux liens différents
 * pour une même vue.
 *
 * L'URL est écrite par l'**historique natif**, pas par `router.push` (#328).
 * `?rank=` n'est lu par aucun rendu serveur : les trois consommateurs
 * (`StatCardsRank`, `ClubPodiumKpi`, `PodiumsList`) le relisent par
 * `useSearchParams` et recalculent en mémoire. Or `/dashboard` et `/club` sont
 * dynamiques et leurs `fetch` passent en `no-store` : un `push` rejouait tout
 * leur rendu serveur — `listEvents(page_size: 200)`, `getStats` et
 * `listSeasons` sur `/dashboard`, plus le `listParticipations(page_size: 1000)`
 * propre à `/club` — pour un résultat que le client tenait déjà. `pushState`
 * s'intègre au routeur Next, donc `useSearchParams` le reflète et retour/avant
 * restent cohérents.
 *
 * Rendu par `SegmentedControl` (`tone="ink"`, #342) plutôt qu'un radiogroup
 * fait main : un `<input type="radio">` masqué par style en ligne
 * (`opacity: 0`) ne peut exprimer `:focus-visible` — focus clavier invisible —
 * et l'ancien fond d'état actif (`--tcn-fill` sur `--tcn-surface`, 1,11:1)
 * n'atteignait pas le seuil de 3:1 pour une information d'état. `SegmentedControl`
 * pose l'actif en encre sur blanc (16,69:1) et rend un `<button>` natif dont le
 * focus se voit nativement (classe `tcn-segmented-btn`).
 *
 * Conteneur en `role="group"`, pas `role="radiogroup"` : ses enfants sont des
 * `<button>` (`aria-pressed`), pas des `role="radio"` — un radiogroup sans
 * enfant radio est une structure ARIA invalide qui rend l'état sélectionné
 * muet pour un lecteur d'écran. Même précédent que `ScopeToggle`.
 */
export function RankTypeToggle() {
  const pathname = usePathname();
  const sp = useSearchParams();
  const active = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);

  function apply(next: RankType) {
    const params = new URLSearchParams(sp.toString());
    if (next === RANK_DEFAULT) params.delete(RANK_PARAM);
    else params.set(RANK_PARAM, next);
    const qs = params.toString();
    window.history.pushState(null, "", `${pathname}${qs ? `?${qs}` : ""}`);
  }

  return (
    <div role="group" aria-label="Type de rang">
      <SegmentedControl
        tone="ink"
        value={active}
        onChange={(next) => apply(next as RankType)}
        options={OPTION_VALUES.map((value) => ({ value, label: rankTypeLabel(value) }))}
      />
    </div>
  );
}
