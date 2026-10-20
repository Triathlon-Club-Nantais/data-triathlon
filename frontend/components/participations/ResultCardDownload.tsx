"use client";

import { useState } from "react";
import { Button } from "@/components/tcn";
import { useHydratedSession } from "@/lib/queries/auth";
import { downloadResultCard, resultCardModel } from "@/lib/result-card";
import type { Participation } from "@/lib/types";

/**
 * « Télécharger l'image » d'un résultat (#1371), pour le seul compte rattaché à
 * la fiche (#1325), sur un résultat validé et individuel : un relais nomme des
 * équipiers, que la carte ne doit pas citer.
 */
export function ResultCardDownload({ participation, libelle = "Télécharger l'image" }: { participation: Participation; libelle?: string }) {
  const session = useHydratedSession();
  const [enCours, setEnCours] = useState(false);
  const [echec, setEchec] = useState<string | null>(null);

  const sienne = session.data?.athlete?.id === participation.athlete.id;
  if (!sienne || participation.is_pending_validation || participation.is_relay) return null;

  async function telecharger() {
    if (enCours) return;
    setEnCours(true);
    setEchec(null);
    try {
      await downloadResultCard(resultCardModel(participation), `resultat-${slug(participation.course.name)}.png`);
    } catch (erreur) {
      setEchec((erreur as Error).message);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <Button variant="secondary" aria-disabled={enCours || undefined} onClick={telecharger}>
        {libelle}
      </Button>
      {echec && (
        <p role="alert" style={{ margin: 0, fontSize: 13, color: "var(--tcn-danger)" }}>
          {echec}
        </p>
      )}
    </div>
  );
}

function slug(texte: string): string {
  return texte
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
