"use client";

import { useState } from "react";
import { Button, Input } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import type { AthleteBrief } from "@/lib/types";

const nomComplet = (a: AthleteBrief) => `${a.prenom} ${a.nom}`;

/**
 * Recherche d'athlète et **choix différé** (#490, PROF-10).
 *
 * Jusqu'à #490 le clic sur un résultat écrivait immédiatement : c'était le
 * quatrième geste d'écriture non hiérarchisé du panneau. Ici il ne fait que
 * *choisir* ; l'enregistrement unique applique.
 */
export function ReattributionField({
  athleteActuel,
  athleteCible,
  onChoisir,
  disabled,
}: {
  athleteActuel: AthleteBrief;
  athleteCible: AthleteBrief | null;
  onChoisir: (athlete: AthleteBrief | null) => void;
  disabled?: boolean;
}) {
  const [recherche, setRecherche] = useState("");
  const [resultats, setResultats] = useState<AthleteBrief[] | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function rechercher(valeur: string) {
    setRecherche(valeur);
    setErreur(null);
    if (valeur.trim().length < 2) {
      setResultats(null);
      return;
    }
    setEnCours(true);
    try {
      setResultats(await apiClient.searchAthletesBenevole(valeur));
    } catch {
      // `null` et non `[]` : rendre une liste vide affichait « aucun coureur
      // trouvé » sur une recherche **en échec** (relevé en revue de #513), et
      // le bénévole en concluait que l'athlète n'existe pas.
      setResultats(null);
      setErreur("Recherche impossible pour le moment. Réessayez dans un instant.");
    } finally {
      setEnCours(false);
    }
  }

  function choisir(athlete: AthleteBrief) {
    setRecherche("");
    setResultats(null);
    onChoisir(athlete);
  }

  if (athleteCible) {
    return (
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Réattribuer à</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <strong>{nomComplet(athleteCible)}</strong>
          <span style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
            au lieu de {nomComplet(athleteActuel)}
          </span>
          <Button variant="ghost" onClick={() => onChoisir(null)} disabled={disabled}>
            Annuler ce choix
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <label
        htmlFor="benevole-reattribution"
        style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}
      >
        Réattribuer à
      </label>
      <Input
        id="benevole-reattribution"
        value={recherche}
        onChange={(e) => rechercher(e.target.value)}
        placeholder="Nom du coureur"
        disabled={disabled}
        aria-describedby={erreur ? "benevole-reattribution-erreur" : undefined}
        style={{ width: "100%" }}
      />
      {enCours && (
        <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>Recherche…</div>
      )}
      {!enCours && resultats !== null && resultats.length === 0 && (
        <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>
          Aucun coureur trouvé.
        </div>
      )}
      {!enCours && resultats !== null && resultats.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
          {resultats.map((athlete) => (
            <button
              key={athlete.id}
              type="button"
              className="tcn-rowlink"
              onClick={() => choisir(athlete)}
              disabled={disabled}
              style={{
                textAlign: "left",
                padding: "8px 12px",
                minHeight: 44,
                border: "1px solid var(--tcn-border)",
                borderRadius: "var(--tcn-radius-md)",
                background: "var(--tcn-surface)",
              }}
            >
              {nomComplet(athlete)}
              {athlete.club && <span style={{ color: "var(--tcn-text-faint)" }}> · {athlete.club}</span>}
            </button>
          ))}
        </div>
      )}
      {erreur && (
        <div
          id="benevole-reattribution-erreur"
          role="alert"
          style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}
        >
          {erreur}
        </div>
      )}
    </div>
  );
}
