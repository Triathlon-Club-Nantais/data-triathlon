import { BarList } from "@/components/charts/BarList";
import { CAT_COLORS } from "@/components/charts/CategoryBars";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { ClubComposition as ClubCompositionData } from "@/lib/types";

/** Codes normalisés par le scraping (`backend/app/scrapers/*.py` : "H" alias de "M"). */
function genderLabel(code: string): string {
  if (code === "M") return "Hommes";
  if (code === "F") return "Femmes";
  return "Non renseigné";
}

/**
 * Couleur de genre — mêmes tokens que `GenderDonut` (`/courses/[id]`), pour
 * qu'« Hommes »/« Femmes » se lisent de la même teinte partout sur le site.
 */
function genderColor(code: string): string {
  if (code === "M") return "var(--tcn-orange)";
  if (code === "F") return "var(--tcn-ink)";
  return "var(--tcn-grey-400)";
}

/**
 * « À quoi ressemble le club ? » (US9, #466) — genre et catégorie d'âge sur
 * l'ensemble du club, pas seulement le top 12 de `ClubSummary.roster` (#581).
 * Un athlète compte une fois, pas une fois par épreuve : la composition porte
 * sur des personnes. Agrégée côté serveur (#642, `ClubSummary.composition`) —
 * `/club` la transporte déjà, aucun fetch ici.
 *
 * Les deux sections sont repliées par défaut (#653) : `Accordion` sans
 * `defaultValue` ouvre sur rien, comportement déjà en place dans
 * `RolePermissionsEditor`. Chaque barre porte sa propre couleur — `colorer`
 * était absent des deux appels à `BarList`, qui retombait sur sa teinte unique
 * par défaut.
 */
export function ClubComposition({ composition }: { composition: ClubCompositionData }) {
  const genderEntries = Object.entries(composition.gender);
  const categoryEntries = Object.entries(composition.category);
  // Couleur positionnelle, comme `CategoryBars` : la même catégorie garde sa
  // couleur tant que l'ordre de `composition.category` ne change pas.
  const categoryColorByKey = new Map(
    categoryEntries.map(([key], index) => [key, CAT_COLORS[index % CAT_COLORS.length]]),
  );

  return (
    // `multiple` : « Par genre » et « Par catégorie » sont deux sections
    // indépendantes, pas des alternatives — les replier l'une l'autre à
    // l'ouverture surprendrait (comportement par défaut d'Accordion, hérité
    // de `RolePermissionsEditor`, où les rôles sont bien des alternatives).
    <Accordion multiple className="space-y-4">
      <AccordionItem value="genre">
        <AccordionTrigger className="cursor-pointer text-sm font-semibold text-[var(--tcn-text-faint)] hover:no-underline">
          Par genre
        </AccordionTrigger>
        <AccordionContent>
          <BarList
            entries={genderEntries}
            labeller={genderLabel}
            colorer={genderColor}
            emptyTitle="Aucun athlète"
            subjectLabel="genre"
          />
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="categorie">
        <AccordionTrigger className="cursor-pointer text-sm font-semibold text-[var(--tcn-text-faint)] hover:no-underline">
          Par catégorie
        </AccordionTrigger>
        <AccordionContent>
          <BarList
            entries={categoryEntries}
            labeller={(k) => k || "Non renseignée"}
            colorer={(k) => categoryColorByKey.get(k) ?? "var(--tcn-grey-300)"}
            emptyTitle="Aucune catégorie renseignée"
            subjectLabel="catégorie"
          />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
