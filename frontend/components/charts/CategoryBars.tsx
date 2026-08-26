import Link from "next/link";
import { scaleLinear } from "d3-scale";
import { pctFr } from "@/lib/utils/format";
import { EmptyState } from "@/components/ui/empty-state";
import { categoryTitle } from "@/lib/categories";

/** « Autres (500) » se dit « Autres » à l'oreille : le compte suit déjà en pourcentage. */
function nomCourt(name: string): string {
  return name.replace(/\s*\(\d+\)$/, "");
}

const CAT_COLORS = [
  "var(--tcn-orange)", "var(--tcn-orange-300)", "var(--tcn-ink)", "var(--tcn-ink-2)",
  "var(--tcn-ink-3)", "var(--tcn-grey-400)", "var(--tcn-orange-200)", "var(--tcn-grey-300)",
];

/**
 * Barres de répartition par catégorie (`/courses/[id]`). `total` est la somme
 * de **toutes** les catégories (`categories_total` de l'API), pas la somme
 * des catégories passées ici — sinon chaque barre se gonfle (cf. page test).
 */
export function CategoryBars({
  categories,
  total,
  hrefFor,
  highlight,
}: {
  categories: { name: string; count: number }[];
  total: number;
  /**
   * Rend chaque barre activable vers le classement filtré sur cette catégorie
   * (#486, RES-11). Absent, la carte reste une image — c'est le cas partout où
   * il n'y a pas de classement à filtrer en dessous.
   */
  hrefFor?: (name: string) => string;
  /** Catégorie de l'athlète consultant l'écran (US3, #466) : marquée dans la barre et le résumé, sans effet si absente des catégories affichées. */
  highlight?: string;
}) {
  if (categories.length === 0) {
    return <EmptyState bare className="px-0 py-4" title="Catégories non renseignées" />;
  }

  const scale = total > 0 ? scaleLinear().domain([0, total]).range([0, 100]) : () => 0;

  // Ce que les barres affichées ne couvrent pas (#486, RES-7). Sur la course 27,
  // les huit barres du top ne portent que 70,1 % des participants — 29,9 %
  // n'apparaissaient nulle part, et l'écran laissait croire à un tout. Omise
  // quand elle est nulle (rien à dessiner) ou négative (le dénominateur publié
  // est incohérent : mieux vaut se taire que mentir dans l'autre sens).
  const reste = total - categories.reduce((somme, c) => somme + c.count, 0);
  const barres =
    reste > 0 ? [...categories, { name: `Autres (${reste})`, count: reste }] : categories;

  const summary = barres
    .map((c) => `${nomCourt(c.name)} ${pctFr(scale(c.count))} %${c.name === highlight ? " (votre catégorie)" : ""}`)
    .join(", ");

  // Sans lien, la carte est une image et se lit d'un bloc. Avec, elle devient une
  // liste de contrôles : la donner encore pour une image masquerait chaque lien au
  // lecteur d'écran. Une vraie `<ul>` dans ce cas — `role="list"` sur un `div` tient,
  // mais l'élément natif évite d'avoir à poser `listitem` à la main sur des `<li>`.
  const Conteneur = hrefFor ? "ul" : "div";

  return (
    <Conteneur
      // La `<ul>` porte déjà son rôle de liste ; seul le `div` a besoin qu'on lui
      // dise qu'il est une image.
      role={hrefFor ? undefined : "img"}
      aria-label={
        hrefFor
          ? // La répartition **entière** reste annoncée, part « Autres » comprise :
            // c'est elle que RES-7 rend visible, et la reléguer à la variante non
            // navigable la retirerait précisément de l'écran pour lequel elle a été
            // écrite (relevé en revue de code).
            `Répartition par catégorie : ${summary}. Chaque barre filtre le classement.`
          : `Répartition par catégorie : ${summary}.`
      }
      style={{ display: "flex", flexDirection: "column", gap: 10, listStyle: "none", margin: 0, padding: 0 }}
    >
      {barres.map((c, i) => {
        const pct = scale(c.count);
        // La barre « Autres » porte un compte entre parenthèses : elle déborde
        // les 36 px calibrés pour « S1 », d'où la piste élargie pour elle seule.
        // Elle n'est jamais activable : « Autres » n'est pas une catégorie, et
        // aucun filtre ne saurait la reproduire.
        const estReste = i === categories.length;
        const href = !estReste && hrefFor ? hrefFor(c.name) : null;
        const isHighlighted = highlight != null && c.name === highlight;

        const barre = (
          <>
            <span
              aria-hidden
              // Largeur **identique pour toutes les lignes**, et calibrée sur la plus
              // longue — « Autres (500) ». Une piste `flex: 1` se résout contre ce
              // qui reste : élargir ce seul libellé raccourcissait sa piste de 16 à
              // 25 % selon la largeur de carte, si bien qu'une part de 29,9 % s'y
              // dessinait à la longueur d'un 22 %. C'est l'honnêteté même que RES-7
              // devait rétablir qui se perdait au tracé.
              //
              // 36 px suffisaient pour « S1 » mais pas pour les codes en mots que
              // portent les données (« M SENIOR », « F VETERAN », ~58 px) : sans
              // `overflow`, ils débordaient sur la piste. L'ellipse les borne, et le
              // libellé complet reste dans le `title` et le nom accessible du lien.
              style={{ flex: "none", width: 84, fontWeight: 800, fontSize: 13, color: estReste ? "var(--tcn-text-muted)" : "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
              title={estReste ? undefined : c.name}
            >
              {c.name}
            </span>
            <div style={{ flex: 1, height: 13, background: "var(--tcn-fill)", borderRadius: 999, overflow: "hidden" }}>
              <div
                style={{
                  width: pct + "%",
                  height: "100%",
                  // `CAT_COLORS` compte exactement `_MAX_CATEGORIES` entrées : la
                  // barre « Autres », en position 8, reprenait `8 % 8 = 0`, soit
                  // l'orange de la **plus grosse** catégorie. Les deux barres les
                  // plus larges de la carte se peignaient de la même couleur, dans
                  // un graphique où elle est le seul différenciateur.
                  background: estReste ? "var(--tcn-grey-300)" : CAT_COLORS[i % CAT_COLORS.length],
                  borderRadius: 999,
                }}
              />
            </div>
            <span aria-hidden style={{ flex: "none", width: 48, textAlign: "right", fontSize: 13, fontWeight: 700, color: "var(--tcn-text-body)" }}>
              {pctFr(pct)}%
            </span>
          </>
        );

        // `minHeight: 24` : plancher tactile WCAG 2.2 2.5.8 — la barre ne fait
        // que 13 px de haut.
        const ligne = {
          display: "flex",
          alignItems: "center",
          gap: 10,
          minHeight: 24,
          // Catégorie de l'athlète consultant l'écran (US3, #466) : seul signal
          // visuel, sans dépendre de la couleur seule (WCAG 1.4.1).
          ...(isHighlighted
            ? { outline: "2px solid var(--tcn-orange)", borderRadius: 8, padding: "2px 4px" }
            : undefined),
        } as const;

        if (!href) {
          // La barre « Autres » n'est pas activable, mais elle porte du sens : ses
          // trois spans sont `aria-hidden`, donc son nom accessible vient d'ici —
          // sans quoi elle serait un élément de liste muet.
          const contenu = (
            <div
              aria-label={hrefFor ? `${nomCourt(c.name)}, ${pctFr(pct)} %` : undefined}
              data-highlighted={isHighlighted ? "true" : undefined}
              style={ligne}
            >
              {barre}
            </div>
          );
          return hrefFor ? <li key={c.name}>{contenu}</li> : <div key={c.name}>{contenu}</div>;
        }

        // Le libellé complet vit dans le nom accessible du lien **et** dans son
        // `title` : au clavier comme au doigt, l'activer ou le focaliser annonce
        // « V2 — Vétéran 2 », là où une infobulle de survol seule n'existerait
        // ni pour l'un ni pour l'autre (FR-028).
        const titre = categoryTitle(c.name);
        // Un `<li>` réel, jamais `role="listitem"` posé sur le `Link` — le rôle
        // explicite écraserait `link` et le contrôle disparaîtrait de l'arbre. Et
        // pas de conteneur en `display: contents` non plus : selon le moteur il
        // peut être retiré de l'arbre, laissant une liste sans enfants.
        return (
          <li key={c.name}>
          <Link
            href={href}
            title={titre}
            aria-label={`${titre} — ${pctFr(pct)} %. Voir ces participants dans le classement.`}
            className="tcn-rowlink"
            data-highlighted={isHighlighted ? "true" : undefined}
            style={{ ...ligne, color: "inherit", textDecoration: "none" }}
          >
            {barre}
            {/* Affordance : `.tcn-rowlink` ne pose qu'un survol à 1,05:1 sur une
                carte blanche — « littéralement invisible » selon globals.css — et
                rien du tout au doigt. Le chevron reprend le patron de fin de ligne
                d'`EventList`, seul signal qui dise qu'une statistique mène quelque
                part. */}
            <span aria-hidden style={{ flex: "none", color: "var(--tcn-text-disabled)", fontSize: 13 }}>
              →
            </span>
          </Link>
          </li>
        );
      })}
    </Conteneur>
  );
}
