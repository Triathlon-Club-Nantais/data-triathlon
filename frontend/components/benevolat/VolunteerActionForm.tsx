"use client";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Card, Input } from "@/components/tcn";
import { useDebounce } from "@/hooks/useDebounce";
import { apiClient } from "@/lib/api/client";
import { useCreateVolunteerAction } from "@/lib/queries/volunteer-actions";
import type { AthleteBrief } from "@/lib/types";

const nomComplet = (a: AthleteBrief) => `${a.prenom} ${a.nom}`;

/**
 * Formulaire public self-service — crédite l'athlète choisi pour le quota de
 * saison (#778), seul chemin de déclaration de bénévolat depuis le retrait
 * de l'auto-déclaration (#751, #816).
 *
 * Recherche : patron `ReattributionField.tsx` (débounce 300 ms, seuil 2
 * caractères, anti-course par jeton) adapté à `searchAthletesConnected`
 * (`GET /athletes`, research.md D2 — pas le twin `/benevoles/athletes`, la
 * page vit déjà sous `(public_restricted)`).
 */
export function VolunteerActionForm() {
  const [recherche, setRecherche] = useState("");
  const [resultats, setResultats] = useState<AthleteBrief[] | null>(null);
  const [rechercheErreur, setRechercheErreur] = useState<string | null>(null);
  const [rechercheEnCours, setRechercheEnCours] = useState(false);
  const [athlete, setAthlete] = useState<AthleteBrief | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const descriptionId = useId();
  const rechercheErreurId = useId();
  const debounced = useDebounce(recherche, 300);
  const requestTokenRef = useRef(0);
  const create = useCreateVolunteerAction();

  useEffect(() => {
    if (recherche.trim().length >= 2) return;
    requestTokenRef.current++;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResultats(null);
    setRechercheErreur(null);
    setRechercheEnCours(false);
  }, [recherche]);

  useEffect(() => {
    if (debounced.trim().length < 2) return;

    const token = ++requestTokenRef.current;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRechercheErreur(null);
    setRechercheEnCours(true);
    apiClient
      .searchAthletesConnected(debounced)
      .then((resultSet) => {
        if (token === requestTokenRef.current) setResultats(resultSet);
      })
      .catch(() => {
        // `null` et non `[]` : rendre une liste vide affichait « aucun
        // athlète trouvé » sur une recherche en échec (même piège relevé en
        // #513 sur ReattributionField.tsx) — un membre en conclurait que
        // l'athlète n'existe pas plutôt que de réessayer.
        if (token === requestTokenRef.current) {
          setResultats(null);
          setRechercheErreur("Recherche impossible pour le moment. Réessayez dans un instant.");
        }
      })
      .finally(() => {
        if (token === requestTokenRef.current) setRechercheEnCours(false);
      });
  }, [debounced]);

  function choisir(choix: AthleteBrief) {
    setAthlete(choix);
    setRecherche("");
    setResultats(null);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!athlete) {
      setErreur("Choisissez d'abord un athlète.");
      return;
    }
    if (!title.trim() || !description.trim()) {
      setErreur("Le titre et la description sont obligatoires.");
      return;
    }
    setErreur(null);
    try {
      await create.mutateAsync({
        athlete_id: athlete.id,
        title: title.trim(),
        description: description.trim(),
      });
      setAthlete(null);
      setTitle("");
      setDescription("");
      toast.success("Déclaration enregistrée, en attente de validation.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {athlete ? (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Athlète</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <strong>{nomComplet(athlete)}</strong>
              <Button variant="ghost" onClick={() => setAthlete(null)} disabled={create.isPending}>
                Changer d&apos;athlète
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <label
              htmlFor="benevolat-athlete"
              style={{ display: "block", fontWeight: 700, marginBottom: 6 }}
            >
              Athlète
            </label>
            <Input
              id="benevolat-athlete"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Nom du coureur"
              aria-describedby={rechercheErreur ? rechercheErreurId : undefined}
            />
            {rechercheEnCours && (
              <div role="status" style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>
                Recherche…
              </div>
            )}
            {rechercheErreur && (
              <div
                id={rechercheErreurId}
                role="alert"
                style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}
              >
                {rechercheErreur}
              </div>
            )}
            {!rechercheEnCours && !rechercheErreur && resultats !== null && resultats.length === 0 && (
              <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, marginTop: 8 }}>
                Aucun athlète trouvé.
              </div>
            )}
            {resultats !== null && resultats.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                {resultats.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    className="tcn-rowlink"
                    onClick={() => choisir(a)}
                    style={{
                      textAlign: "left",
                      padding: "8px 12px",
                      minHeight: 44,
                      border: "1px solid var(--tcn-border)",
                      borderRadius: "var(--tcn-radius-md)",
                    }}
                  >
                    {nomComplet(a)}
                    {a.club && <span style={{ color: "var(--tcn-text-faint)" }}> · {a.club}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <div>
          <label htmlFor="benevolat-action-titre" style={{ display: "block", fontWeight: 700, marginBottom: 6 }}>
            Titre
          </label>
          <Input
            id="benevolat-action-titre"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex. Ravitaillement 10km du Lac"
            maxLength={200}
          />
        </div>
        <div>
          <label htmlFor={descriptionId} style={{ display: "block", fontWeight: 700, marginBottom: 6 }}>
            Description
          </label>
          <textarea
            id={descriptionId}
            className="tcn-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Décrivez l'activité de bénévolat effectuée"
            maxLength={10000}
            rows={4}
            style={{ width: "100%", resize: "vertical" }}
          />
        </div>
        {erreur && (
          <p role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 14, margin: 0 }}>
            {erreur}
          </p>
        )}
        <Button
          type="submit"
          disabled={create.isPending}
          aria-busy={create.isPending}
          style={{ alignSelf: "flex-start" }}
        >
          Déclarer pour cet athlète
        </Button>
      </form>
    </Card>
  );
}
