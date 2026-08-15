"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessGate } from "@/components/benevoles/AccessGate";
import { ParticipationPanel } from "@/components/benevoles/ParticipationPanel";
import { ValidationQueue } from "@/components/benevoles/ValidationQueue";
import { Eyebrow } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";

type Etat = "chargement" | "gate" | "file" | "erreur";

/**
 * Page de vérification des résultats par les bénévoles (#271).
 *
 * Hors `/admin/*` et hors `nav.config.ts` — accès direct par URL communiquée
 * aux bénévoles, protégé par mot de passe partagé plutôt que par SSO
 * (research.md §D1 de la feature).
 */
export default function BenevolesPage() {
  const [etat, setEtat] = useState<Etat>("chargement");
  const [participations, setParticipations] = useState<Participation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const chargerLaFile = useCallback(async () => {
    try {
      const resultats = await apiClient.getBenevoleQueue();
      setParticipations(resultats);
      setEtat("file");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setEtat("gate");
      } else {
        setEtat("erreur");
      }
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    chargerLaFile();
  }, [chargerLaFile]);

  function surChangement(mise_a_jour: Participation) {
    if (!mise_a_jour.is_pending_validation) {
      setParticipations((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setSelectedId((id) => (id === mise_a_jour.id ? null : id));
      return;
    }
    setParticipations((liste) => liste.map((p) => (p.id === mise_a_jour.id ? mise_a_jour : p)));
  }

  if (etat === "chargement") {
    return null;
  }

  if (etat === "gate") {
    return <AccessGate onSuccess={chargerLaFile} />;
  }

  if (etat === "erreur") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        La file de validation n&apos;a pas pu être chargée. Réessayez plus tard.
      </div>
    );
  }

  const selectionnee = participations.find((p) => p.id === selectedId) ?? null;

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: "0 24px" }}>
      <Eyebrow style={{ marginBottom: 6 }}>Bénévoles</Eyebrow>
      <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(26px, 4vw, 34px)", color: "var(--tcn-ink)", marginBottom: 24 }}>
        Vérification des résultats
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 360px) 1fr", gap: 24, alignItems: "start" }}>
        <ValidationQueue participations={participations} selectedId={selectedId} onSelect={setSelectedId} />
        {selectionnee ? (
          <ParticipationPanel participation={selectionnee} onChanged={surChangement} />
        ) : (
          <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, padding: 24 }}>
            Sélectionnez un résultat dans la file pour le relire.
          </div>
        )}
      </div>
    </div>
  );
}
