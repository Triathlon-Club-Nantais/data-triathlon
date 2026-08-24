import { scaleLinear } from "d3-scale";
import { formatMonthShort } from "@/lib/utils/date";

/**
 * Histogramme vertical de l'activité par mois (12 derniers mois présents).
 * Server-compatible (pas de dépendance graphique externe).
 */
export function MonthlyTrend({ byMonth }: { byMonth: Record<string, number> }) {
  const entries = Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-12);

  if (entries.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-[var(--tcn-text-faint)]">
        Pas encore de données mensuelles.
      </p>
    );
  }

  const max = Math.max(1, ...entries.map(([, v]) => v));

  // d3-scale ne fait que la partie linéaire (0→max sur 0→100) ; le plancher de
  // 4 % pour rester visible à zéro reste un `Math.max` explicite au point
  // d'usage — ce n'est PAS un `range([4, 100])`, qui décalerait toutes les
  // valeurs intermédiaires (`range([4,100])` donne 52 % pour une valeur moitié
  // du max, pas 50 % : deux formules différentes, pas juste deux écritures).
  const heightScale = scaleLinear().domain([0, max]).range([0, 100]);

  // `role="img"` élague tous les descendants de l'arbre d'accessibilité : sans
  // énumération ici, les douze couples mois/valeur — pourtant lisibles à
  // l'écran — disparaissent pour un lecteur d'écran (#480). Même patron que
  // `DisciplineBar`, `BarList` et `CategoryBars` : « X : liste. ».
  const summary = entries
    .map(([key, value]) => `${formatMonthShort(key)} ${value}`)
    .join(", ");

  return (
    <div
      role="img"
      aria-label={`Activité mensuelle : ${summary}.`}
      className="flex h-44 items-end gap-1.5"
    >
      {entries.map(([key, value], index) => (
        <div key={key} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1.5">
          {/* Valeur toujours écrite : `opacity-0` + `group-hover` n'existent pas
              au doigt, et l'attribut `title` non plus (WCAG 1.4.13, #480). */}
          <span
            aria-hidden
            className="num whitespace-nowrap text-[11px] font-bold text-[var(--tcn-text-faint)]"
          >
            {value}
          </span>
          <div
            className="w-full rounded-t-sm bg-[color-mix(in_oklch,var(--primary)_70%,transparent)]"
            style={{ height: `${Math.max(4, heightScale(value))}%` }}
          />
          {/* Le texte est TOUJOURS rendu : `.micro-label` n'a ni `min-height`
              ni `display`, donc un span vide a une hauteur de 0 et décale sa
              barre d'une colonne sur deux (#480) — c'est pour réserver cette
              hauteur, et non pour restituer de la largeur, que le libellé
              reste rendu même masqué : `visibility: hidden` ne rend aucune
              largeur, contrairement à ce qu'un lecteur pourrait supposer. Le
              masquage un-mois-sur-deux (`max-sm:invisible`) ne vaut que sous
              `sm:`, pour que les libellés restés visibles ne se touchent pas
              — douze tiennent très bien sur la carte desktop. Compté depuis
              la fin pour que le plus récent soit toujours écrit. Sans
              `min-w-0`, `flex: 1 1 0%` garde `min-width: auto` : les douze
              boîtes imposeraient leur largeur min-content à la rangée et,
              sur téléphone, l'`overflow-hidden` de la Card écrêterait sans
              scroll les colonnes de trop — précisément les mois les plus
              récents (#480). `whitespace-nowrap`, sur ce libellé et sur la
              valeur au-dessus, les fait déborder proprement de leur colonne
              plutôt que de se casser en plusieurs lignes, ce qui décalerait
              l'alignement des barres. */}
          <span
            aria-hidden
            data-month-label
            className={`micro-label whitespace-nowrap text-[var(--tcn-text-faint)] ${
              (entries.length - 1 - index) % 2 === 0 ? "" : "max-sm:invisible"
            }`}
          >
            {formatMonthShort(key)}
          </span>
        </div>
      ))}
    </div>
  );
}
