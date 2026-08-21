"use client";

import { useState } from "react";
import { Button, Card, Input } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";
import type { AthleteBrief, Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";

/** Détail d'un résultat en attente : relecture, renommage, réattribution, validation (#271). */
export function ParticipationPanel({
  participation,
  onChanged,
  onSessionExpired,
}: {
  participation: Participation;
  onChanged: (updated: Participation) => void;
  /** Le cookie a expiré ou le mot de passe a changé pendant que l'écran était ouvert. */
  onSessionExpired?: () => void;
}) {
  const [erreurValidation, setErreurValidation] = useState<string | null>(null);
  const [enCoursValidation, setEnCoursValidation] = useState(false);

  const [nomEpreuve, setNomEpreuve] = useState(participation.course.name);
  const [erreurRenommage, setErreurRenommage] = useState<string | null>(null);
  const [enCoursRenommage, setEnCoursRenommage] = useState(false);

  const [rechercheAthlete, setRechercheAthlete] = useState("");
  const [resultatsAthletes, setResultatsAthletes] = useState<AthleteBrief[] | null>(null);
  const [rechercheEnCours, setRechercheEnCours] = useState(false);
  const [erreurReattribution, setErreurReattribution] = useState<string | null>(null);
  const [enCoursReattribution, setEnCoursReattribution] = useState(false);

  const [champs, setChamps] = useState({
    bib_number: participation.bib_number ?? "",
    rank_overall: participation.rank_overall != null ? String(participation.rank_overall) : "",
    club: participation.club ?? "",
    category: participation.category ?? "",
  });
  const [erreurChamps, setErreurChamps] = useState<string | null>(null);
  const [enCoursChamps, setEnCoursChamps] = useState(false);

  const [confirmationRejet, setConfirmationRejet] = useState(false);
  const [erreurRejet, setErreurRejet] = useState<string | null>(null);
  const [enCoursRejet, setEnCoursRejet] = useState(false);

  /** Une session expirée prévient le parent plutôt que d'afficher une erreur générique
   *  sur un geste qui ne peut plus aboutir — sinon le bénévole reste bloqué sur cet
   *  écran jusqu'au rechargement manuel de la page (revue de code). */
  function gererErreur(err: unknown, setErreur: (message: string) => void, repli: string) {
    if (err instanceof ApiError && err.status === 401) {
      onSessionExpired?.();
      return;
    }
    setErreur(err instanceof ApiError ? err.message : repli);
  }

  async function valider() {
    setErreurValidation(null);
    setEnCoursValidation(true);
    try {
      const resultat = await apiClient.validateParticipationBenevole(participation.id);
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurValidation, "La validation a échoué. Réessayez plus tard.");
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
      gererErreur(err, setErreurRenommage, "Le renommage a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRenommage(false);
    }
  }

  async function rechercher(valeur: string) {
    setRechercheAthlete(valeur);
    setErreurReattribution(null);
    if (valeur.trim().length < 2) {
      setResultatsAthletes(null);
      return;
    }
    setRechercheEnCours(true);
    try {
      setResultatsAthletes(await apiClient.searchAthletesBenevole(valeur));
    } catch {
      // `null` et non `[]` : rendre une liste vide affichait « aucun coureur
      // trouvé » sur une recherche **en échec** (relevé en revue de #513), et
      // le bénévole en concluait que l'athlète n'existe pas.
      setResultatsAthletes(null);
      setErreurReattribution("Recherche impossible pour le moment. Réessayez dans un instant.");
    } finally {
      setRechercheEnCours(false);
    }
  }

  async function reattribuer(athlete: AthleteBrief) {
    setErreurReattribution(null);
    setEnCoursReattribution(true);
    try {
      const resultat = await apiClient.reassignParticipationBenevole(participation.id, athlete.id);
      setResultatsAthletes(null);
      setRechercheAthlete("");
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurReattribution, "La réattribution a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursReattribution(false);
    }
  }

  async function enregistrerChamps() {
    setErreurChamps(null);
    setEnCoursChamps(true);
    try {
      const resultat = await apiClient.updateParticipationFieldsBenevole(participation.id, {
        bib_number: champs.bib_number || null,
        rank_overall: champs.rank_overall ? Number(champs.rank_overall) : null,
        club: champs.club || null,
        category: champs.category || null,
      });
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurChamps, "L'enregistrement a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursChamps(false);
    }
  }

  async function signalerNonConforme() {
    setErreurRejet(null);
    setEnCoursRejet(true);
    try {
      const resultat = await apiClient.rejectParticipationBenevole(participation.id);
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurRejet, "Le signalement a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRejet(false);
      setConfirmationRejet(false);
    }
  }

  async function annulerLeRejet() {
    setErreurRejet(null);
    setEnCoursRejet(true);
    try {
      const resultat = await apiClient.unrejectParticipationBenevole(participation.id);
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurRejet, "L'annulation a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRejet(false);
    }
  }

  return (
    <Card padding={24}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 20, color: "var(--tcn-ink)", fontWeight: 400, margin: 0 }}>
            {participation.athlete.prenom} {participation.athlete.nom}
          </h2>
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
              <a href={participation.evidence_url!} target="_blank" rel="noopener noreferrer" className="tcn-rowlink hover:underline">
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

        {participation.is_rejected && (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Annulez d&apos;abord le rejet pour modifier ce résultat.
          </div>
        )}

        {!participation.is_rejected && (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16 }}>
            <label htmlFor="benevole-nom-epreuve" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              Nom de l&apos;épreuve
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <Input
                id="benevole-nom-epreuve"
                value={nomEpreuve}
                onChange={(e) => setNomEpreuve(e.target.value)}
                aria-describedby={erreurRenommage ? "benevole-nom-epreuve-erreur" : undefined}
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
              <div id="benevole-nom-epreuve-erreur" role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>
                {erreurRenommage}
              </div>
            )}
          </div>
        )}

        {!participation.is_rejected && (
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
              aria-describedby={erreurReattribution ? "benevole-reattribution-erreur" : undefined}
              style={{ width: "100%" }}
            />
            {rechercheEnCours && (
              <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>Recherche…</div>
            )}
            {!rechercheEnCours && resultatsAthletes !== null && resultatsAthletes.length === 0 && (
              <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>
                Aucun coureur trouvé.
              </div>
            )}
            {!rechercheEnCours && resultatsAthletes !== null && resultatsAthletes.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                {resultatsAthletes.map((athlete) => (
                  <button
                    key={athlete.id}
                    type="button"
                    className="tcn-rowlink"
                    onClick={() => reattribuer(athlete)}
                    disabled={enCoursReattribution}
                    style={{ textAlign: "left", padding: "8px 12px", minHeight: 44, border: "1px solid var(--tcn-border)", borderRadius: "var(--tcn-radius-md)", background: "var(--tcn-surface)" }}
                  >
                    {athlete.prenom} {athlete.nom}
                    {athlete.club && <span style={{ color: "var(--tcn-text-faint)" }}> · {athlete.club}</span>}
                  </button>
                ))}
              </div>
            )}
            {erreurReattribution && (
              <div id="benevole-reattribution-erreur" role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>
                {erreurReattribution}
              </div>
            )}
          </div>
        )}

        {!participation.is_rejected && (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label htmlFor="benevole-dossard" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Dossard
                </label>
                <Input
                  id="benevole-dossard"
                  value={champs.bib_number}
                  onChange={(e) => setChamps((c) => ({ ...c, bib_number: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="benevole-place" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Place au général
                </label>
                <Input
                  id="benevole-place"
                  type="number"
                  value={champs.rank_overall}
                  onChange={(e) => setChamps((c) => ({ ...c, rank_overall: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="benevole-club" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Club
                </label>
                <Input
                  id="benevole-club"
                  value={champs.club}
                  onChange={(e) => setChamps((c) => ({ ...c, club: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="benevole-categorie" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Catégorie
                </label>
                <Input
                  id="benevole-categorie"
                  value={champs.category}
                  onChange={(e) => setChamps((c) => ({ ...c, category: e.target.value }))}
                />
              </div>
            </div>
            <Button variant="secondary" onClick={enregistrerChamps} disabled={enCoursChamps} style={{ marginTop: 12 }}>
              {enCoursChamps ? "Enregistrement…" : "Enregistrer les modifications"}
            </Button>
            {erreurChamps && (
              <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>
                {erreurChamps}
              </div>
            )}
          </div>
        )}

        <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          {!participation.is_rejected && (
            <Button onClick={valider} disabled={enCoursValidation} style={{ width: "100%" }}>
              {enCoursValidation ? "Validation…" : "Valider ce résultat"}
            </Button>
          )}
          {erreurValidation && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreurValidation}
            </div>
          )}
          {participation.is_rejected ? (
            <Button variant="secondary" onClick={annulerLeRejet} disabled={enCoursRejet} style={{ width: "100%" }}>
              {enCoursRejet ? "Annulation…" : "Annuler le rejet"}
            </Button>
          ) : !confirmationRejet ? (
            <Button
              variant="secondary"
              onClick={() => setConfirmationRejet(true)}
              style={{ width: "100%", color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-border)" }}
            >
              Signaler non conforme
            </Button>
          ) : (
            <div style={{ display: "flex", gap: 8 }}>
              <Button
                variant="secondary"
                onClick={signalerNonConforme}
                disabled={enCoursRejet}
                style={{ flex: 1, color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-border)" }}
              >
                {enCoursRejet ? "Signalement…" : "Confirmer ?"}
              </Button>
              <Button variant="ghost" onClick={() => setConfirmationRejet(false)} disabled={enCoursRejet} style={{ flex: 1 }}>
                Annuler
              </Button>
            </div>
          )}
          {erreurRejet && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreurRejet}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
