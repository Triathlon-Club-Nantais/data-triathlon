"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useId, useState } from "react";
import { AnnonceStatut, Button, Card } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { PublicPageSettings } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

const CIBLE = { className: "tcn-cible-tactile", style: { display: "flex", alignItems: "center", gap: 8 } } as const;
const MASQUES = [
  ["hide_best_times", "Masquer mes records"],
  ["hide_progression", "Masquer ma progression"],
  ["hide_comparison", "Masquer la comparaison"],
] as const;
const NB_LIENS = 3;

/** « Ma fiche publique » (#1692) : ce que mon compte rattaché montre sur sa fiche d'athlète. */
export function MaFichePublique({ athleteId }: { athleteId: number }) {
  const reglages = useQuery({
    queryKey: queryKeys.publicPageSettings(),
    queryFn: () => apiClient.getPublicPageSettings(),
    retry: false,
  });
  if (reglages.isPending) return null;
  if (reglages.error) {
    return (
      <Card>
        <p role="alert" style={{ margin: 0 }}>{reglages.error.message}</p>
      </Card>
    );
  }
  return <Formulaire athleteId={athleteId} initial={reglages.data} />;
}

function Formulaire({ athleteId, initial }: { athleteId: number; initial: PublicPageSettings }) {
  const ids = useId();
  const qc = useQueryClient();
  const [masques, setMasques] = useState({
    hide_best_times: initial.hide_best_times,
    hide_progression: initial.hide_progression,
    hide_comparison: initial.hide_comparison,
  });
  const [liens, setLiens] = useState(() => Array.from({ length: NB_LIENS }, (_, i) => initial.links[i] ?? ""));
  const [epingle, setEpingle] = useState(initial.pinned_participation_id);
  const [annonce, setAnnonce] = useState("");

  // Pas de filtre : toute la carrière, comme la fiche publique.
  const carriere = useQuery({
    queryKey: ["mon-espace", "fiche-publique-resultats", athleteId],
    queryFn: () => apiClient.getAthlete(athleteId),
    retry: false,
  });
  const resultats = (carriere.data?.participations ?? []).filter((p) => !p.is_pending_validation);

  const enregistrer = useMutation({
    mutationFn: () =>
      apiClient.savePublicPageSettings({
        ...masques,
        links: liens.map((l) => l.trim()).filter(Boolean),
        pinned_participation_id: epingle,
      }),
    onMutate: () => setAnnonce(""),
    onSuccess: () => {
      setAnnonce("Réglages enregistrés.");
      return qc.invalidateQueries({ queryKey: queryKeys.publicPageSettings() });
    },
  });

  return (
    <Card>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>
        Ma fiche publique
      </h2>
      <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>
        Masquer un bloc n&apos;efface rien : vos résultats restent publics et permettent de le recalculer.{" "}
        <Link href={`/athletes/${athleteId}`} className="underline underline-offset-2">Voir ma fiche</Link>
      </p>
      {initial.shared && (
        <p style={{ margin: "8px 0 0", fontSize: 13 }}>
          Plusieurs comptes sont rattachés à votre fiche : vos liens, votre objectif et votre résultat épinglé n&apos;y sont pas affichés.
        </p>
      )}
      <form
        onSubmit={(e) => { e.preventDefault(); if (!enregistrer.isPending) enregistrer.mutate(); }}
        style={{ marginTop: 16, display: "grid", gap: 12, maxWidth: 420 }}
      >
        {MASQUES.map(([cle, libelle]) => (
          <label key={cle} {...CIBLE}>
            <input type="checkbox" checked={masques[cle]} onChange={(e) => setMasques({ ...masques, [cle]: e.target.checked })} />
            {libelle}
          </label>
        ))}
        {liens.map((lien, i) => (
          <div key={i} style={{ display: "grid", gap: 4 }}>
            <label htmlFor={`${ids}-lien-${i}`} style={{ fontWeight: 600 }}>Lien {i + 1} (Strava, Garmin, Polar ou Suunto)</label>
            <input
              id={`${ids}-lien-${i}`}
              type="url"
              className="tcn-input"
              maxLength={200}
              placeholder="https://www.strava.com/athletes/…"
              value={lien}
              onChange={(e) => setLiens(liens.map((l, j) => (j === i ? e.target.value : l)))}
            />
          </div>
        ))}
        <label htmlFor={`${ids}-epingle`} style={{ fontWeight: 600 }}>Résultat épinglé</label>
        <select
          id={`${ids}-epingle`}
          className="tcn-input"
          value={epingle === null ? "" : String(epingle)}
          onChange={(e) => setEpingle(e.target.value === "" ? null : Number(e.target.value))}
        >
          <option value="">Aucun</option>
          {resultats.map((p) => (
            <option key={p.id} value={p.id}>
              {p.course.name}{p.course.event_date ? `, ${formatDate(p.course.event_date)}` : ""}
            </option>
          ))}
        </select>
        {enregistrer.error && (
          <p role="alert" style={{ margin: 0, color: "var(--tcn-danger)", fontSize: 13 }}>{enregistrer.error.message}</p>
        )}
        <AnnonceStatut texte={annonce} />
        <div>
          <Button type="submit" aria-disabled={enregistrer.isPending || undefined}>Enregistrer</Button>
        </div>
      </form>
    </Card>
  );
}
