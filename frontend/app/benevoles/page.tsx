"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { AccessGate } from "@/components/benevoles/AccessGate";
import { ParticipationPanel } from "@/components/benevoles/ParticipationPanel";
import { useFileValidation } from "@/components/benevoles/useFileValidation";
import { ValidationQueue } from "@/components/benevoles/ValidationQueue";
import { AnnonceStatut, Eyebrow, Button } from "@/components/tcn";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useEstCompact } from "@/hooks/useEstCompact";
import type { Participation } from "@/lib/types";

/**
 * Page de vérification des résultats par les bénévoles (#271).
 *
 * Hors `/admin/*` et hors `nav.config.ts` — accès direct par URL communiquée
 * aux bénévoles, protégé par mot de passe partagé plutôt que par SSO
 * (research.md §D1 de la feature).
 *
 * Depuis #490 (PROF-9) la file s'enchaîne : la validation d'une entrée
 * sélectionne la suivante, au lieu de laisser le bénévole repointer à la main.
 */
export default function BenevolesPage() {
  const file = useFileValidation();
  const compact = useEstCompact();
  const [feuilleOuverte, setFeuilleOuverte] = useState(false);
  /** Une ref plutôt qu'un état : le garde-fou est lu dans un gestionnaire de
   *  clic, jamais rendu — un état ne ferait que déclencher un rendu de plus. */
  const brouillonSale = useRef(false);
  /**
   * `components/admin/DangerConfirm.tsx` — le seul mécanisme de confirmation
   * du dépôt, jamais `window.confirm` : ce dernier n'est ni traduisible, ni
   * stylable, ni testable, et sur téléphone il s'ouvre par-dessus la feuille
   * modale sans que le produit ne le contrôle (#490, revue UI/UX, item 2). Le
   * `DangerConfirmProvider` qu'exige ce hook vit dans `layout.tsx`, à côté de
   * cette page : premier appelant hors `/admin` (revue de #499).
   */
  const confirmer = useDangerConfirm();

  const surBrouillonSale = useCallback((sale: boolean) => {
    brouillonSale.current = sale;
  }, []);

  async function selectionner(id: number) {
    // Un simple ré-appui sur l'entrée déjà sélectionnée (rouvrir la feuille
    // fermée, par ex.) n'est pas un changement d'entrée : le panneau reste
    // monté (`keepMounted` sur la feuille) et son brouillon éventuel avec
    // lui, donc `brouillonSale` ne doit ni être questionné ni remis à `false`
    // — le remettre à `false` sur un ré-appui désynchroniserait le témoin du
    // vrai état du panneau, qui lui n'a pas changé (revue de #490 ronde 1).
    const changeDEntree = id !== file.selectedId;
    if (changeDEntree && brouillonSale.current) {
      const ok = await confirmer({
        titre: "Abandonner les modifications non enregistrées ?",
        description: "Ce résultat porte des modifications non enregistrées.",
        libelleAction: "Abandonner",
      });
      if (!ok) return;
    }
    if (changeDEntree) brouillonSale.current = false;
    file.selectionner(id);
    if (compact) setFeuilleOuverte(true);
  }

  function surChangement(maj: Participation) {
    brouillonSale.current = false;
    file.surChangement(maj);
  }

  /**
   * Focus et scroll suivent l'enchaînement (WCAG 2.4.3), pas seulement la
   * première sélection (#490, revue UI/UX, item 1).
   *
   * Le panneau est démonté et remonté à chaque changement d'entrée
   * (`key={file.selectionnee.id}`) : le bouton qui portait le focus disparaît
   * avec lui et le focus retombe sur `<body>`, obligeant à retabuler depuis le
   * sommet du document sur le geste le plus fréquent de l'écran. Sous `md`,
   * la feuille (`overflow-y-auto`) est le conteneur de défilement et son
   * `scrollTop` survit à l'échange d'enfant : la validation se fait depuis la
   * barre collante, donc en bas — la nouvelle entrée s'ouvrait sur ses champs
   * et sa barre d'action plutôt que sur le nom de l'athlète.
   *
   * Seul un **remplacement** d'entrée déjà affichée est concerné
   * (`precedent` et `courant` tous deux non nuls et distincts) : la toute
   * première sélection n'a pas besoin de ce recentrage, son propre geste s'en
   * charge déjà — l'ouverture de la feuille pour le tactile, le bouton de la
   * file resté focus pour le bureau (`PROF-9`, déjà traitée).
   */
  const idPrecedent = useRef<number | null>(null);
  useEffect(() => {
    const precedent = idPrecedent.current;
    const courant = file.selectionnee?.id ?? null;
    idPrecedent.current = courant;
    if (precedent === null || courant === null || precedent === courant) return;
    const feuille = document.querySelector('[data-slot="sheet-content"]');
    if (feuille) feuille.scrollTop = 0;
    document.getElementById("benevole-panel-titre")?.focus();
  }, [file.selectionnee?.id]);

  if (file.etat === "chargement") {
    // `role="status"` + `<h1>` : un « Chargement… » nu n'était ni annoncé ni
    // identifié — l'écran perdait jusqu'à son titre pendant l'attente (#490,
    // revue UI/UX, P2).
    return (
      <div role="status" style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(26px, 4vw, 34px)", color: "var(--tcn-ink)", marginBottom: 8, fontWeight: 400 }}>
          Vérification des résultats
        </h1>
        Chargement…
      </div>
    );
  }

  if (file.etat === "gate") {
    return <AccessGate onSuccess={file.charger} />;
  }

  if (file.etat === "erreur") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        {/* « Réessayez plus tard » juste au-dessus d'un bouton qui invite à
            réessayer *maintenant* se contredisait (#490, revue UI/UX, P2). */}
        <div style={{ marginBottom: 16 }}>La file n&apos;a pas pu être chargée.</div>
        <Button variant="secondary" onClick={file.charger}>
          Réessayer
        </Button>
      </div>
    );
  }

  const panneau = file.selectionnee ? (
    <ParticipationPanel
      key={file.selectionnee.id}
      participation={file.selectionnee}
      onChanged={surChangement}
      onSessionExpired={file.surSessionExpiree}
      onBrouillonSale={surBrouillonSale}
    />
  ) : null;

  // Sous `md` le panneau vit dans une feuille modale : le reste du document
  // (donc cette région) n'est jamais garanti d'être annoncé par un lecteur
  // d'écran une fois la feuille ouverte. L'annonce voyage avec la feuille
  // plutôt que de rester dans l'arbre principal, sans jamais être rendue deux
  // fois (#490, revue de branche finale).
  const annonce = <AnnonceStatut texte={file.annonce} />;

  // Une file non vide (file **ou** non-conformes) laisse toujours quelque
  // chose à sélectionner ; une file entièrement épuisée ne doit pas
  // contredire l'état de réussite affiché à côté par `ValidationQueue`
  // (#490, revue de branche finale).
  const quelqueChoseASelectionner = file.participations.length > 0 || file.rejetees.length > 0;

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: "0 24px" }}>
      <Eyebrow style={{ marginBottom: 6 }}>Bénévoles</Eyebrow>
      <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(26px, 4vw, 34px)", color: "var(--tcn-ink)", marginBottom: 24, fontWeight: 400 }}>
        Vérification des résultats
      </h1>
      {/* Le toast passe inaperçu d'un lecteur d'écran : la même phrase vit ici
          en région `status` (WCAG 4.1.3, patron `AnnonceStatut`). Seulement
          au-dessus de `md` : sous `md` l'annonce vit dans la feuille. */}
      {!compact && annonce}
      <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-[minmax(280px,360px)_1fr]">
        <ValidationQueue
          participations={file.participations}
          rejected={file.rejetees}
          selectedId={file.selectedId}
          onSelect={selectionner}
          traitees={file.traitees}
        />
        {compact ? (
          <Sheet open={feuilleOuverte && panneau !== null} onOpenChange={setFeuilleOuverte}>
            {/* `keepMounted` : Échap ou un tap hors de la feuille la ferment
                sans confirmation (aucun des deux n'est désactivé), et par
                défaut `Popup`/`Portal` démontent alors `ParticipationPanel`
                — avec lui le brouillon de `useBrouillon`, en silence. La
                feuille reste montée (juste masquée) à la fermeture ; seul un
                changement d'entrée via `selectionner` peut encore abandonner
                un brouillon, et seulement après confirmation (#490, revue
                ronde 1). */}
            <SheetContent side="right" className="w-full overflow-y-auto p-4" keepMounted>
              {/* La largeur ne fige plus `max-w-[520px]` : sous 520px de
                  viewport — tous les téléphones — cette valeur remplaçait
                  entièrement le `max-w-[85%]` de la primitive (`cn` fait un
                  `twMerge`, pas une union) et couvrait tout l'écran, sans
                  bande de fond restant tactile pour fermer la feuille. Un
                  `SheetClose` explicite couvre le cas général ; garder
                  `max-w-[85%]` garde aussi une bande de secours (#490, revue
                  de branche finale). */}
              <div className="flex items-center justify-between">
                {/* `sr-only`, pas `fontSize: 0` : certaines combinaisons
                    navigateur/lecteur d'écran traitent une taille de police
                    nulle comme « pas rendu », laissant le dialogue sans nom
                    accessible (#490, revue UI/UX, item 9). */}
                <SheetTitle className="sr-only">Détail du résultat</SheetTitle>
                {/* `size-11` (44×44) plutôt que le `p-2.5` suggéré en revue :
                    avec l'icône `size-4` (16 px), un padding de 10 px de
                    chaque côté ne totalise que 36 px, sous le plancher WCAG
                    2.5.8 — une dimension fixe l'atteint quelle que soit
                    l'icône, comme la croix analogue d'`AppNav.tsx` (#490,
                    revue UI/UX, item 4). `.tcn-icon-btn` porte le survol et
                    l'anneau de focus ; `hover:` seul ne réagit jamais au
                    tactile. */}
                <SheetClose
                  aria-label="Fermer le détail du résultat"
                  className="tcn-icon-btn flex size-11 items-center justify-center rounded-full text-[var(--tcn-text-faint)] hover:text-[var(--tcn-ink)]"
                >
                  <X className="size-4" />
                </SheetClose>
              </div>
              {compact && annonce}
              {panneau}
            </SheetContent>
          </Sheet>
        ) : (
          (panneau ?? (quelqueChoseASelectionner ? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, padding: 24 }}>
              Sélectionnez un résultat dans la file pour le relire.
            </div>
          ) : null))
        )}
      </div>
    </div>
  );
}
