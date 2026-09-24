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
/** Taille de page de `GET /admin/athletes` : une liste pleine est peut-être tronquée. */
const PAGE_CANDIDATS = 20;

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
  const champRecherche = `equipiers-${resultat.id}`;
  const proposes = (candidats.data ?? []).filter((c) => !equipe.some((e) => e.id === c.id));

  // Ajouter ou retirer fait disparaître le bouton qui portait le focus : il
  // revient sur la recherche, point de départ du geste suivant (WCAG 2.4.3).
  function refocaliser() {
    document.getElementById(champRecherche)?.focus();
  }
  const quand = formatDate(resultat.date);
  const intitule = quand ? `« ${resultat.epreuve} — ${quand} »` : `« ${resultat.epreuve} »`;

  function ajouter(membre: Membre) {
    setRefus(null);
    setEquipe((actuelle) =>
      actuelle.some((e) => cle(e) === cle(membre)) || actuelle.length >= MAX_EQUIPIERS
        ? actuelle
        : [...actuelle, membre],
    );
    refocaliser();
  }

  function ajouterLaPersonne() {
    ajouter({ id: null, nom: nouveauNom.trim(), prenom: nouveauPrenom.trim() });
    setNouveauNom("");
    setNouveauPrenom("");
  }

  function retirer(membre: Membre) {
    setRefus(null);
    setEquipe((actuelle) => actuelle.filter((e) => cle(e) !== cle(membre)));
    refocaliser();
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
      // 409 (coureur déjà classé), 404 (fiche disparue) et 400 (refus métier)
      // portent un message français du serveur qui dit quoi corriger.
      if (erreur instanceof ApiError && [400, 404, 409].includes(erreur.status)) {
        setRefus(erreur.message);
        return;
      }
      toast.error(ECHEC);
    }
  }

  const avis =
    refus ??
    (equipe.length === 0 ? `Ajoutez au moins ${MIN_EQUIPIERS} coureurs pour attribuer ce relais.` : null) ??
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
            {attribution.isPending ? "Attribution…" : "Attribuer"}
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
            htmlFor={champRecherche}
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
            id={champRecherche}
            type="search"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            placeholder="Chercher un coureur par nom ou prénom…"
            autoComplete="off"
            disabled={attribution.isPending || complete}
          />
        </div>

        {/* Un formulaire pour que Entrée ajoute depuis Nom ou Prénom. */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (nouveauNom.trim() && nouveauPrenom.trim() && !complete) ajouterLaPersonne();
          }}
        >
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
              type="submit"
              variant="secondary"
              size="sm"
              disabled={
                !nouveauNom.trim() || !nouveauPrenom.trim() || attribution.isPending || complete
              }
            >
              Ajouter ce coureur
            </Button>
          </div>
        </fieldset>
        </form>

        {/* Région live montée en permanence, texte vide au repos : une région
            insérée avec son texte n'est pas annoncée. */}
        <div role="status" aria-live="polite">
          {avis && (
            <p style={{ fontSize: 13, color: "var(--tcn-text-muted)", margin: 0 }}>{avis}</p>
          )}
          {!complete && candidats.isFetching && (
            <p style={{ fontSize: 13, color: "var(--tcn-text-faint)", margin: 0 }}>Recherche…</p>
          )}
          {!complete && candidats.data?.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--tcn-text-faint)", margin: 0 }}>
              Aucun coureur ne correspond à cette recherche.
            </p>
          )}
          {!complete && candidats.data && candidats.data.length >= PAGE_CANDIDATS && (
            <p style={{ fontSize: 13, color: "var(--tcn-text-muted)", margin: 0 }}>
              Seuls les {PAGE_CANDIDATS} premiers coureurs sont listés : précisez la recherche si le
              bon n&apos;y est pas.
            </p>
          )}
        </div>

        {!complete && proposes.length > 0 && (
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
            {proposes.map((candidat) => (
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
