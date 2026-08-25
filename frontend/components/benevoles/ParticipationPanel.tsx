"use client";

import { useEffect, useState } from "react";
import { Button, Card } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";
import { ChampsParticipation } from "./ChampsParticipation";
import { ReattributionField } from "./ReattributionField";
import { useBrouillon } from "./useBrouillon";

/**
 * Détail d'un résultat en attente : relecture, correction, validation (#271).
 *
 * Depuis #490 (PROF-10) le panneau n'a plus qu'**un** état de formulaire, **un**
 * enregistrement et **une** zone d'erreur, et son action primaire vit dans une
 * barre collante plutôt qu'en dernière position du DOM.
 */
export function ParticipationPanel({
  participation,
  onChanged,
  onSessionExpired,
  onBrouillonSale,
}: {
  participation: Participation;
  onChanged: (updated: Participation) => void;
  /** Le cookie a expiré ou le mot de passe a changé pendant que l'écran était ouvert. */
  onSessionExpired?: () => void;
  /** La page en fait son garde-fou : on ne quitte pas une entrée sale sans confirmer. */
  onBrouillonSale?: (sale: boolean) => void;
}) {
  const { brouillon, modifier, sale, erreur, enCours, validationEnCours, enregistrer, validerLeResultat } =
    useBrouillon(participation, { onChanged, onSessionExpired });

  const [confirmationRejet, setConfirmationRejet] = useState(false);
  const [erreurRejet, setErreurRejet] = useState<string | null>(null);
  const [enCoursRejet, setEnCoursRejet] = useState(false);

  useEffect(() => {
    onBrouillonSale?.(sale);
  }, [sale, onBrouillonSale]);

  // Une seule zone d'erreur pour deux familles d'actions distinctes (le
  // brouillon via `useBrouillon`, le rejet géré ici) : chacune efface l'erreur
  // de l'*autre* au moment où elle démarre, jamais la sienne propre — `occupe`
  // interdit déjà qu'elles tournent en même temps, donc au plus une des deux
  // erreurs est posée quand ce rendu a lieu (#490, revue de #490). `modifier({})`
  // ne change aucun champ : c'est la seule façon d'atteindre le `setErreur(null)`
  // interne du hook sans dupliquer sa logique dans ce composant.
  const erreurAffichee = erreur ?? erreurRejet;

  function modifierEtEffacerErreurRejet(patch: Parameters<typeof modifier>[0]) {
    setErreurRejet(null);
    modifier(patch);
  }

  function enregistrerEnEffacantErreurRejet() {
    setErreurRejet(null);
    return enregistrer();
  }

  function validerEnEffacantErreurRejet() {
    setErreurRejet(null);
    return validerLeResultat();
  }

  async function agirSurLeRejet(action: "rejeter" | "annuler") {
    modifier({});
    setErreurRejet(null);
    setEnCoursRejet(true);
    try {
      onChanged(
        action === "rejeter"
          ? await apiClient.rejectParticipationBenevole(participation.id)
          : await apiClient.unrejectParticipationBenevole(participation.id),
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onSessionExpired?.();
        return;
      }
      setErreurRejet(err instanceof ApiError ? err.message : "L'opération a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRejet(false);
      setConfirmationRejet(false);
    }
  }

  const rejetee = participation.is_rejected === true;
  const occupe = enCours || enCoursRejet;

  return (
    <Card padding={24}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          {/* `id` + `tabIndex={-1}` : cible de focus programmatique après un
              enchaînement (#490, revue UI/UX, item 1) — jamais dans l'ordre de
              tabulation naturel. Un seul panneau est monté à la fois (desktop
              ou feuille, jamais les deux), l'`id` fixe ne collisionne donc
              jamais. `.tcn-panel-titre` lui donne le même anneau de focus que
              `.tcn-btn` : sans classe dédiée il retomberait sur l'anneau
              universel `outline-ring/50`, à 1,86:1 (#342). */}
          <h2
            id="benevole-panel-titre"
            tabIndex={-1}
            className="tcn-panel-titre"
            style={{ fontFamily: "var(--tcn-font-display)", fontSize: 20, color: "var(--tcn-ink)", fontWeight: 400, margin: 0 }}
          >
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

        {rejetee ? (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, color: "var(--tcn-text-faint)", fontSize: 14 }}>
            Levez d&apos;abord le signalement pour modifier ce résultat.
          </div>
        ) : (
          <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
            <ChampsParticipation
              brouillon={brouillon}
              origine={participation}
              onChange={modifierEtEffacerErreurRejet}
              disabled={occupe}
            />
            <ReattributionField
              athleteActuel={participation.athlete}
              athleteCible={brouillon.athlete_cible}
              onChoisir={(athlete) => modifierEtEffacerErreurRejet({ athlete_cible: athlete })}
              disabled={occupe}
            />
          </div>
        )}

        {/* Barre d'action collante : l'action primaire est unique, visible et
            sur le chemin de lecture — elle était la dernière du DOM, donc hors
            écran au chargement sur mobile (#490, PROF-10). */}
        <div
          style={{
            position: "sticky",
            bottom: 0,
            background: "var(--tcn-surface)",
            borderTop: "1px solid var(--tcn-border)",
            paddingTop: 16,
            marginTop: 4,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {sale && (
            <div style={{ fontSize: 13, color: "var(--tcn-text-body)", fontWeight: 600 }}>
              Modifications non enregistrées
            </div>
          )}
          {erreurAffichee && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreurAffichee}
            </div>
          )}
          {!rejetee && (
            <>
              <Button onClick={validerEnEffacantErreurRejet} disabled={occupe} style={{ width: "100%" }}>
                {validationEnCours ? "Validation…" : "Valider ce résultat"}
              </Button>
              <Button
                variant="secondary"
                onClick={enregistrerEnEffacantErreurRejet}
                disabled={occupe || !sale}
                style={{ width: "100%" }}
              >
                {/* Chaque bouton porte son propre indicatif d'attente : `enCours`
                    reste vrai pendant tout `validerLeResultat` (l'éventuel
                    `enregistrer()` compris), donc sans `!validationEnCours` un
                    clic sur « Valider » affichait « Enregistrement… » sur le
                    bouton « Enregistrer », que personne n'avait pressé (#490,
                    revue UI/UX, item 5). */}
                {enCours && !validationEnCours ? "Enregistrement…" : "Enregistrer"}
              </Button>
            </>
          )}
          {rejetee ? (
            <Button variant="secondary" onClick={() => agirSurLeRejet("annuler")} disabled={occupe} style={{ width: "100%" }}>
              {enCoursRejet ? "Levée du signalement…" : "Lever le signalement"}
            </Button>
          ) : !confirmationRejet ? (
            <Button
              variant="secondary"
              onClick={() => setConfirmationRejet(true)}
              disabled={occupe}
              // Bordure en `--tcn-danger-text` (5,28:1 sur `--tcn-surface`), pas
              // `--tcn-danger-border` (1,60:1, sous le seuil WCAG 1.4.11 de 3:1
              // pour un contour de composant) : à côté d'« Enregistrer » cerné
              // de noir plein, le geste destructif se voyait à peine (#490,
              // revue UI/UX, item 3).
              style={{ width: "100%", color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-text)" }}
            >
              Signaler non conforme
            </Button>
          ) : (
            <>
              {/* Rejeter n'enregistre rien : sans cet avertissement, un
                  brouillon sale était abandonné en silence, exactement la
                  perte de saisie que #490 (PROF-10) ferme côté validation
                  (#490, revue de branche finale). */}
              {sale && (
                <div style={{ fontSize: 13, color: "var(--tcn-danger-text)" }}>
                  Les modifications non enregistrées seront perdues.
                </div>
              )}
              {/* Colonne, pas ligne : à 360 px de large, deux pistes `flex: 1`
                  n'ont que 69 px de glyphes pour « Confirmer le signalement »
                  et « Signalement… », et `.tcn-btn` interdit le retour à la
                  ligne (`white-space: nowrap`) — le débordement horizontal de
                  la feuille se déclenchait exactement en confirmant un
                  signalement (#490, revue UI/UX, item 6). */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <Button
                  variant="secondary"
                  onClick={() => agirSurLeRejet("rejeter")}
                  disabled={occupe}
                  style={{ width: "100%", color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-text)" }}
                >
                  {/* Vocabulaire unifié sur « non conforme »/« signalement » —
                      « Confirmer ? » ne nommait pas son geste, et voisinait
                      « Annuler le rejet »/« Annulez d'abord le rejet », la
                      famille de mots que l'écran avait par ailleurs
                      abandonnée (#490, revue UI/UX, item 7). */}
                  {enCoursRejet ? "Signalement…" : "Confirmer le signalement"}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmationRejet(false)} disabled={occupe} style={{ width: "100%" }}>
                  Revenir
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </Card>
  );
}
