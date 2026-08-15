"use client";

import { useState } from "react";
import { Button, Card, Input } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";
import type { AthleteBrief, Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";

function messageErreur(err: unknown, repli: string): string {
  return err instanceof ApiError ? err.message : repli;
}

/** Détail d'un résultat en attente : relecture, renommage, réattribution, validation (#271). */
export function ParticipationPanel({
  participation,
  onChanged,
}: {
  participation: Participation;
  onChanged: (updated: Participation) => void;
}) {
  const [erreurValidation, setErreurValidation] = useState<string | null>(null);
  const [enCoursValidation, setEnCoursValidation] = useState(false);

  const [nomEpreuve, setNomEpreuve] = useState(participation.course.name);
  const [erreurRenommage, setErreurRenommage] = useState<string | null>(null);
  const [enCoursRenommage, setEnCoursRenommage] = useState(false);

  const [rechercheAthlete, setRechercheAthlete] = useState("");
  const [resultatsAthletes, setResultatsAthletes] = useState<AthleteBrief[]>([]);
  const [erreurReattribution, setErreurReattribution] = useState<string | null>(null);
  const [enCoursReattribution, setEnCoursReattribution] = useState(false);

  async function valider() {
    setErreurValidation(null);
    setEnCoursValidation(true);
    try {
      const resultat = await apiClient.validateParticipationBenevole(participation.id);
      onChanged(resultat);
    } catch (err) {
      setErreurValidation(messageErreur(err, "La validation a échoué. Réessayez plus tard."));
    } finally {
      setEnCoursValidation(false);
    }
  }

  async function enregistrerNom() {
    setErreurRenommage(null);
    setEnCoursRenommage(true);
    try {
      const course = await apiClient.renameCourseBenevole(participation.course.id, nomEpreuve);
      onChanged({ ...participation, course });
    } catch (err) {
      setErreurRenommage(messageErreur(err, "Le renommage a échoué. Réessayez plus tard."));
    } finally {
      setEnCoursRenommage(false);
    }
  }

  async function rechercher(valeur: string) {
    setRechercheAthlete(valeur);
    setErreurReattribution(null);
    if (valeur.trim().length < 2) {
      setResultatsAthletes([]);
      return;
    }
    try {
      setResultatsAthletes(await apiClient.searchAthletes(valeur));
    } catch {
      setResultatsAthletes([]);
    }
  }

  async function reattribuer(athlete: AthleteBrief) {
    setErreurReattribution(null);
    setEnCoursReattribution(true);
    try {
      const resultat = await apiClient.reassignParticipationBenevole(participation.id, athlete.id);
      setResultatsAthletes([]);
      setRechercheAthlete("");
      onChanged(resultat);
    } catch (err) {
      setErreurReattribution(messageErreur(err, "La réattribution a échoué. Réessayez plus tard."));
    } finally {
      setEnCoursReattribution(false);
    }
  }

  return (
    <Card padding={24}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 20, color: "var(--tcn-ink)" }}>
            {participation.athlete.prenom} {participation.athlete.nom}
          </div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-faint)" }}>
            {formatEventName(participation.course.name, participation.course.is_relay)}
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 24px", fontSize: 14 }}>
          <div>
            <span style={{ color: "var(--tcn-text-faint)" }}>Temps : </span>
            <strong>{participation.total_time ?? "—"}</strong>
          </div>
          {participation.team_name && (
            <div>
              <span style={{ color: "var(--tcn-text-faint)" }}>Équipe : </span>
              <strong>{participation.team_name}</strong>
            </div>
          )}
          {isHttpUrl(participation.evidence_url) && (
            <div>
              <a href={participation.evidence_url!} target="_blank" rel="noopener noreferrer" className="hover:underline">
                Lien vers les résultats ↗
              </a>
            </div>
          )}
        </div>

        {participation.splits && Object.keys(participation.splits).length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", fontSize: 13 }}>
            {Object.entries(participation.splits).map(([cle, valeur]) => (
              <div key={cle}>
                <span style={{ color: "var(--tcn-text-faint)" }}>{cle} : </span>
                <strong>{valeur}</strong>
              </div>
            ))}
          </div>
        )}

        <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16 }}>
          <label htmlFor="benevole-nom-epreuve" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            Nom de l&apos;épreuve
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <Input
              id="benevole-nom-epreuve"
              value={nomEpreuve}
              onChange={(e) => setNomEpreuve(e.target.value)}
              containerStyle={{ flex: 1 }}
            />
            <Button
              variant="secondary"
              onClick={enregistrerNom}
              disabled={enCoursRenommage || !nomEpreuve.trim() || nomEpreuve === participation.course.name}
            >
              Enregistrer le nom
            </Button>
          </div>
          {erreurRenommage && (
            <div style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>{erreurRenommage}</div>
          )}
        </div>

        <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16 }}>
          <label htmlFor="benevole-reattribution" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            Réattribuer à
          </label>
          <Input
            id="benevole-reattribution"
            value={rechercheAthlete}
            onChange={(e) => rechercher(e.target.value)}
            placeholder="Nom du coureur"
            disabled={enCoursReattribution}
            style={{ width: "100%" }}
          />
          {resultatsAthletes.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
              {resultatsAthletes.map((athlete) => (
                <button
                  key={athlete.id}
                  type="button"
                  onClick={() => reattribuer(athlete)}
                  disabled={enCoursReattribution}
                  style={{ textAlign: "left", padding: "8px 12px", border: "1px solid var(--tcn-border)", borderRadius: "var(--tcn-radius-md)", background: "var(--tcn-surface)", cursor: "pointer" }}
                >
                  {athlete.prenom} {athlete.nom}
                  {athlete.club && <span style={{ color: "var(--tcn-text-faint)" }}> · {athlete.club}</span>}
                </button>
              ))}
            </div>
          )}
          {erreurReattribution && (
            <div style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>{erreurReattribution}</div>
          )}
        </div>

        <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16 }}>
          <Button onClick={valider} disabled={enCoursValidation} style={{ width: "100%" }}>
            {enCoursValidation ? "Validation…" : "Valider ce résultat"}
          </Button>
          {erreurValidation && (
            <div style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>{erreurValidation}</div>
          )}
        </div>
      </div>
    </Card>
  );
}
