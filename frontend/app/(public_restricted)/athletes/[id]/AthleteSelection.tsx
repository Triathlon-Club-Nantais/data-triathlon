"use client";

import { Button, MetaPill } from "@/components/tcn";
import {
  clearAthlete,
  nomComplet,
  useIsSelectedAthlete,
  writeAthlete,
  type PickedAthlete,
} from "@/components/layout/AthletePicker";

const BENEFICE_ID = "choisir-athlete-benefice";

/**
 * Coin « c'est vous » de l'en-tête du profil : l'état, l'action qui le change,
 * et le bénéfice qui la motive.
 *
 * Choisir/relâcher l'athlète affiché comme athlète retenu, depuis sa page
 * profil (issue #323). `AppNav` reste la seule source de vérité côté
 * navigation — ce bloc se contente de lire/écrire le même stock, via le hook
 * qui l'expose.
 *
 * #467 y ajoute les deux manques relevés par l'audit UX : l'état retenu était
 * seulement **déductible** du libellé du bouton (une commande, pas un état
 * affiché), et rien ne répondait à « pour quoi faire ? » au moment du clic.
 * D'où la pastille permanente et le bénéfice nommé sous le bouton — rattaché
 * en `aria-describedby`, sinon un utilisateur qui tabule jusqu'au bouton ne
 * l'entend jamais.
 *
 * La hiérarchie des boutons s'inverse avec l'état : primaire quand il reste à
 * choisir, secondaire quand il ne reste qu'à révoquer.
 */
export function AthleteSelection({ athlete }: { athlete: PickedAthlete }) {
  const retenu = useIsSelectedAthlete(athlete.id);
  const nom = nomComplet(athlete);

  // Même verbe que l'autre point d'entrée vers cette action (`AthletePicker`
  // aria-label « Choisir {nom} ») — la revue UI/UX a relevé la divergence
  // avec « Sélectionner »/« Relâcher » (issue #323). L'objet de l'action
  // reste nommé même sur l'état retenu, pour un lecteur d'écran qui saute
  // directement au bouton — via `aria-label`. Celui-ci **complète** le texte
  // visible (le nom en suffixe) plutôt que de le remplacer : un `aria-label`
  // qui ne contient plus le texte affiché casse WCAG 2.5.3 pour un
  // utilisateur de commande vocale, qui dit ce qu'il voit à l'écran
  // (relevé en revue UI/UX finale de #752).
  if (retenu) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 10 }}>
        <MetaPill accent dot>
          C&apos;est vous
        </MetaPill>
        <Button
          variant="secondary"
          onClick={() => clearAthlete()}
          aria-label={`Ne plus choisir cet athlète, ${nom}`}
        >
          Ne plus choisir cet athlète
        </Button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8, maxWidth: 300 }}>
      <Button
        variant="primary"
        aria-describedby={BENEFICE_ID}
        aria-label={`Choisir cet athlète, ${nom}`}
        onClick={() => writeAthlete(athlete)}
      >
        Choisir cet athlète
      </Button>
      <p id={BENEFICE_ID} style={{ margin: 0, fontSize: 13, lineHeight: 1.45, color: "var(--tcn-text-muted)" }}>
        Choisir cet athlète pour retrouver ses résultats en un geste et voir sa saison en tête du tableau de bord
      </p>
    </div>
  );
}
