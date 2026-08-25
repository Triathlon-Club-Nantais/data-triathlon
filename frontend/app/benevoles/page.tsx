"use client";

import { useCallback, useRef, useState } from "react";
import { AccessGate } from "@/components/benevoles/AccessGate";
import { ParticipationPanel } from "@/components/benevoles/ParticipationPanel";
import { useFileValidation } from "@/components/benevoles/useFileValidation";
import { ValidationQueue } from "@/components/benevoles/ValidationQueue";
import { AnnonceStatut, Eyebrow, Button } from "@/components/tcn";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
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

  const surBrouillonSale = useCallback((sale: boolean) => {
    brouillonSale.current = sale;
  }, []);

  function selectionner(id: number) {
    if (id !== file.selectedId && brouillonSale.current) {
      const ok = window.confirm(
        "Ce résultat porte des modifications non enregistrées. Les abandonner ?",
      );
      if (!ok) return;
    }
    brouillonSale.current = false;
    file.selectionner(id);
    if (compact) setFeuilleOuverte(true);
  }

  function surChangement(maj: Participation) {
    brouillonSale.current = false;
    file.surChangement(maj);
  }

  if (file.etat === "chargement") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
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
        <div style={{ marginBottom: 16 }}>
          La file de validation n&apos;a pas pu être chargée. Réessayez plus tard.
        </div>
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

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: "0 24px" }}>
      <Eyebrow style={{ marginBottom: 6 }}>Bénévoles</Eyebrow>
      <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(26px, 4vw, 34px)", color: "var(--tcn-ink)", marginBottom: 24, fontWeight: 400 }}>
        Vérification des résultats
      </h1>
      {/* Le toast passe inaperçu d'un lecteur d'écran : la même phrase vit ici
          en région `status` (WCAG 4.1.3, patron `AnnonceStatut`). */}
      <AnnonceStatut texte={file.annonce} />
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
            <SheetContent side="right" className="w-full max-w-[520px] overflow-y-auto p-4">
              <SheetTitle style={{ fontSize: 0 }}>Détail du résultat</SheetTitle>
              {panneau}
            </SheetContent>
          </Sheet>
        ) : (
          (panneau ?? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, padding: 24 }}>
              Sélectionnez un résultat dans la file pour le relire.
            </div>
          ))
        )}
      </div>
    </div>
  );
}
