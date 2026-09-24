"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, Input, Modal } from "@/components/tcn";
import { useDebounce } from "@/hooks/useDebounce";
import { ApiError } from "@/lib/api/client";
import { useAdminAthleteSearch, useSetParticipationTeammates } from "@/lib/queries/admin";
import type { AthleteBrief } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

const MIN_EQUIPIERS = 2;
const MAX_EQUIPIERS = 8;
const ECHEC = "L'attribution n'a pas abouti. Réessayez dans un instant.";

type Equipier = Pick<AthleteBrief, "id" | "nom" | "prenom">;
/** Un coureur choisi par sa fiche, ou saisi par son nom (`id` nul, US2). */
type Membre = { id: number | null; nom: string; prenom: string };

const cle = (m: Membre) => (m.id != null ? `f${m.id}` : `n${m.nom.toLowerCase()}|${m.prenom.toLowerCase()}`);

/**
 * Attribuer un résultat de relais à ses équipiers (#894).
 *
 * La modale part de la composition actuelle : la même commande sert à la
 * première attribution et à sa correction. Sous deux coureurs, le geste n'est
 * pas un relais mais un rattachement, que le serveur refuserait ici : l'écran le
 * dit avant le clic.
 */
export function TeammatesDialog({
  resultat,
  equipiers,
  onClose,
}: {
  resultat: { id: number; epreuve: string; date: string | null };
  equipiers: Equipier[];
  onClose: () => void;
}) {
  const [equipe, setEquipe] = useState<Membre[]>(equipiers);
  const [nouveauNom, setNouveauNom] = useState("");
  const [nouveauPrenom, setNouveauPrenom] = useState("");
  const [saisie, setSaisie] = useState("");
  const [refus, setRefus] = useState<string | null>(null);
  const recherche = useDebounce(saisie, 300);
  const candidats = useAdminAthleteSearch(recherche);
  const attribution = useSetParticipationTeammates();
  const router = useRouter();

  const complete = equipe.length >= MAX_EQUIPIERS;
  const quand = formatDate(resultat.date);
  const intitule = quand ? `« ${resultat.epreuve} — ${quand} »` : `« ${resultat.epreuve} »`;

  function ajouter(membre: Membre) {
    setRefus(null);
    setEquipe((actuelle) =>
      actuelle.some((e) => cle(e) === cle(membre)) || actuelle.length >= MAX_EQUIPIERS
        ? actuelle
        : [...actuelle, membre],
    );
  }

  function ajouterLaPersonne() {
    ajouter({ id: null, nom: nouveauNom.trim(), prenom: nouveauPrenom.trim() });
    setNouveauNom("");
    setNouveauPrenom("");
  }

  function retirer(membre: Membre) {
    setRefus(null);
    setEquipe((actuelle) => actuelle.filter((e) => cle(e) !== cle(membre)));
  }

  async function attribuer() {
    try {
      await attribution.mutateAsync({
        participationId: resultat.id,
        equipiers: equipe.map((e) =>
          e.id != null ? e.id : { athlete_name: e.nom, athlete_firstname: e.prenom },
        ),
      });
      toast.success(`Relais attribué à ${equipe.length} coureurs.`);
      onClose();
      // La fiche courante peut avoir été purgée : `notFound()` prend le relais.
      router.refresh();
    } catch (erreur) {
      // 409 (coureur déjà classé) et 404 (fiche disparue) se corrigent en
      // changeant la composition : le message du serveur nomme le coureur.
      if (erreur instanceof ApiError && (erreur.status === 409 || erreur.status === 404)) {
        setRefus(erreur.message);
        return;
      }
      toast.error(ECHEC);
    }
  }

  const avis =
    refus ??
    (equipe.length === 1 ? "Pour un seul coureur, utilisez « Rattacher »." : null) ??
    (complete ? `Un relais compte au plus ${MAX_EQUIPIERS} coureurs.` : null);

  return (
    <Modal
      eyebrow="Relais"
      title="Attribuer ce relais à ses équipiers"
      onClose={() => (attribution.isPending ? null : onClose())}
      footer={
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Button variant="ghost" onClick={onClose} disabled={attribution.isPending}>
            Annuler
          </Button>
          <Button
            onClick={attribuer}
            disabled={equipe.length < MIN_EQUIPIERS || attribution.isPending}
          >
            Attribuer
          </Button>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--tcn-text-body)", margin: 0 }}>
          {intitule} apparaîtra sur la fiche de chaque coureur choisi. Une fiche au nom de
          l&apos;équipe qui n&apos;a plus aucun résultat sera supprimée.
        </p>

        <ul
          aria-label="Équipe"
          style={{ display: "flex", flexDirection: "column", gap: 6, margin: 0, padding: 0, listStyle: "none" }}
        >
          {equipe.map((equipier) => (
            <li
              key={cle(equipier)}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
            >
              <span style={{ fontWeight: 600 }}>
                {equipier.nom} {equipier.prenom}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => retirer(equipier)}
                disabled={attribution.isPending}
                aria-label={`Retirer ${equipier.nom} ${equipier.prenom}`}
              >
                Retirer
              </Button>
            </li>
          ))}
        </ul>

        <div>
          <label
            htmlFor={`equipiers-${resultat.id}`}
            style={{
              display: "block",
              marginBottom: 6,
              fontSize: 13,
              fontWeight: 700,
              color: "var(--tcn-text-muted)",
            }}
          >
            Ajouter un coureur
          </label>
          <Input
            id={`equipiers-${resultat.id}`}
            type="search"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            placeholder="Chercher un coureur par nom ou prénom…"
            autoComplete="off"
            disabled={attribution.isPending || complete}
          />
        </div>

        <fieldset style={{ border: 0, margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          <legend style={{ fontSize: 13, fontWeight: 700, color: "var(--tcn-text-muted)", marginBottom: 6 }}>
            Coureur sans fiche
          </legend>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, flex: "1 1 140px" }}>
              Nom
              <Input
                value={nouveauNom}
                onChange={(e) => setNouveauNom(e.target.value)}
                autoComplete="off"
                disabled={attribution.isPending || complete}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, flex: "1 1 140px" }}>
              Prénom
              <Input
                value={nouveauPrenom}
                onChange={(e) => setNouveauPrenom(e.target.value)}
                autoComplete="off"
                disabled={attribution.isPending || complete}
              />
            </label>
            <Button
              variant="secondary"
              size="sm"
              onClick={ajouterLaPersonne}
              disabled={
                !nouveauNom.trim() || !nouveauPrenom.trim() || attribution.isPending || complete
              }
            >
              Ajouter cette personne
            </Button>
          </div>
        </fieldset>

        {/* Région live montée en permanence, texte vide au repos : une région
            insérée avec son texte n'est pas annoncée. */}
        <div role="status" aria-live="polite">
          {avis && (
            <p style={{ fontSize: 13, color: "var(--tcn-text-muted)", margin: 0 }}>{avis}</p>
          )}
        </div>

        {!complete && candidats.data && candidats.data.length > 0 && (
          <ul
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              maxHeight: 220,
              overflowY: "auto",
              listStyle: "none",
              margin: 0,
              padding: 0,
            }}
          >
            {candidats.data
              .filter((candidat) => !equipe.some((e) => e.id === candidat.id))
              .map((candidat) => (
                <li key={candidat.id}>
                  <button
                    type="button"
                    className="tcn-rowlink"
                    onClick={() => ajouter({ id: candidat.id, nom: candidat.nom, prenom: candidat.prenom })}
                    disabled={attribution.isPending}
                    aria-label={`Ajouter ${candidat.nom} ${candidat.prenom}`}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "8px 12px",
                      minHeight: 44,
                      border: "1px solid var(--tcn-text-faint)",
                      borderRadius: "var(--tcn-radius-md)",
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>
                      {candidat.nom} {candidat.prenom}
                    </span>
                    <span style={{ display: "block", fontSize: 12, color: "var(--tcn-text-faint)" }}>
                      {candidat.birth_date
                        ? `Né(e) le ${formatDate(candidat.birth_date)}`
                        : "Date de naissance inconnue"}
                      {candidat.club ? ` · ${candidat.club}` : ""}
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}
