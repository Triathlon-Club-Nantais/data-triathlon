"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessGate } from "@/components/benevoles/AccessGate";
import { ParticipationPanel } from "@/components/benevoles/ParticipationPanel";
import { ValidationQueue } from "@/components/benevoles/ValidationQueue";
import { Eyebrow, Button } from "@/components/tcn";
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
  const [rejetees, setRejetees] = useState<Participation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const chargerLaFile = useCallback(async () => {
    setEtat("chargement");
    try {
      const [resultats, rejets] = await Promise.all([
        apiClient.getBenevoleQueue(),
        apiClient.getBenevoleRejected(),
      ]);
      setParticipations(resultats);
      setRejetees(rejets);
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
      // Validée : sort des deux listes.
      setParticipations((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setRejetees((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setSelectedId((id) => (id === mise_a_jour.id ? null : id));
      return;
    }
    if (mise_a_jour.is_rejected) {
      // Vient d'être rejetée : sort de la file, entre dans les non-conformes.
      setParticipations((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setRejetees((liste) => [mise_a_jour, ...liste.filter((p) => p.id !== mise_a_jour.id)]);
      return;
    }
    // Rejet annulé : sort des non-conformes, revient dans la file.
    setRejetees((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
    setParticipations((liste) =>
      liste.some((p) => p.id === mise_a_jour.id)
        ? liste.map((p) => (p.id === mise_a_jour.id ? mise_a_jour : p))
        : [mise_a_jour, ...liste],
    );
  }

  /** Cookie expiré ou mot de passe changé pendant que l'écran était ouvert (#271, revue de code). */
  function surSessionExpiree() {
    setEtat("gate");
  }

  if (etat === "chargement") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        Chargement…
      </div>
    );
  }

  if (etat === "gate") {
    return <AccessGate onSuccess={chargerLaFile} />;
  }

  if (etat === "erreur") {
    return (
      <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center", color: "var(--tcn-text-faint)" }}>
        <div style={{ marginBottom: 16 }}>
          La file de validation n&apos;a pas pu être chargée. Réessayez plus tard.
        </div>
        <Button variant="secondary" onClick={chargerLaFile}>
          Réessayer
        </Button>
      </div>
    );
  }

  const selectionnee =
    participations.find((p) => p.id === selectedId) ?? rejetees.find((p) => p.id === selectedId) ?? null;

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", padding: "0 24px" }}>
      <Eyebrow style={{ marginBottom: 6 }}>Bénévoles</Eyebrow>
      <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(26px, 4vw, 34px)", color: "var(--tcn-ink)", marginBottom: 24, fontWeight: 400 }}>
        Vérification des résultats
      </h1>
      <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-[minmax(280px,360px)_1fr]">
        <ValidationQueue
          participations={participations}
          rejected={rejetees}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {selectionnee ? (
          <ParticipationPanel
            key={selectionnee.id}
            participation={selectionnee}
            onChanged={surChangement}
            onSessionExpired={surSessionExpiree}
          />
        ) : (
          <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, padding: 24 }}>
            Sélectionnez un résultat dans la file pour le relire.
          </div>
        )}
      </div>
    </div>
  );
}
