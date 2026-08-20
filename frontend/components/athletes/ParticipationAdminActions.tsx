"use client";
import { useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { ArrowRightLeft, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button, Input, Modal } from "@/components/tcn";
import { useDebounce } from "@/hooks/useDebounce";
import { ApiError } from "@/lib/api/client";
import {
  useAdminAthleteSearch,
  useDeleteParticipation,
  useReassignParticipation,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import type { AdminAthlete } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

export type ResultatACorriger = {
  id: number;
  /** Nom de l'épreuve — ce que la confirmation doit nommer. */
  epreuve: string;
  /** `event_date` de l'épreuve, au format ISO ; formatée à l'affichage. */
  date: string | null;
  /** Nom complet du coureur dont la fiche perd le résultat. */
  coureur: string;
  /** Fiche qui porte le résultat aujourd'hui — celle qu'on ne se rattache pas. */
  coureurId: number;
};

/** Un `404` décrit une requête ; l'opérateur, lui, voit un écran (FR-016). */
const DISPARU = "Ce résultat n'existe plus. La page a été mise à jour.";
const ECHEC = "La suppression n'a pas abouti. Réessayez dans un instant.";
const ECHEC_RATTACHEMENT = "Le rattachement n'a pas abouti. Réessayez dans un instant.";
/** Une demande sans effet n'est pas un échec — le serveur la traite en `200`. */
const DEJA_PORTE = "Ce résultat est déjà au nom de ce coureur.";

/**
 * Actions d'administration d'**un** résultat, sous sa ligne (#439).
 *
 * Rendu en sous-ligne du tableau et jamais à l'intérieur du `<Link>` de la
 * ligne : un `<button>` dans une ancre est du HTML invalide, ce pour quoi le
 * lien « Voir la preuve » occupe déjà sa propre sous-ligne (D9).
 *
 * **Le composant porte lui-même le conteneur de la sous-ligne**, et c'est ce qui
 * garantit qu'un visiteur sans pouvoir ne voit ni ligne vide ni espace réservé :
 * un conteneur posé par la page resterait rendu, avec ses marges, autour de rien.
 * L'appelant n'en fixe que le calage horizontal, par `style`, pour ne pas
 * dupliquer la constante de padding du tableau.
 *
 * Comme `AthleteAdminPanel`, la visibilité se décide **dans le navigateur**,
 * geste par geste, et une session illisible n'offre rien (FR-008). Les vingt
 * lignes d'une page partagent un seul appel de session : `useSession` a une clé
 * de cache unique.
 */
export function ParticipationAdminActions({
  resultat,
  style,
}: {
  resultat: ResultatACorriger;
  style?: CSSProperties;
}) {
  const session = useSession();
  const pouvoirs = session.data?.permissions;
  const peutSupprimer = pouvoirs?.includes("participations:delete") ?? false;
  // Deux pouvoirs pour un seul geste : le sélecteur ci-dessous lit la recherche
  // gardée par `athletes:read`, seule à rendre la date de naissance. Sans elle,
  // l'action serait annoncée puis finirait en 403 — ce que FR-006 proscrit (D6).
  const peutRattacher =
    (pouvoirs?.includes("participations:reassign") ?? false) &&
    (pouvoirs?.includes("athletes:read") ?? false);

  const [confirmation, setConfirmation] = useState(false);
  const [rattachementOuvert, setRattachementOuvert] = useState(false);
  const [saisie, setSaisie] = useState("");
  const [dejaPorte, setDejaPorte] = useState(false);
  const recherche = useDebounce(saisie, 300);
  const router = useRouter();
  const suppression = useDeleteParticipation();
  const rattachement = useReassignParticipation();
  const candidats = useAdminAthleteSearch(recherche);

  if (!peutSupprimer && !peutRattacher) return null;

  async function supprimer() {
    try {
      await suppression.mutateAsync(resultat.id);
      // Seul retour explicite quand la ligne était en attente de validation :
      // elle ne compte dans aucun des cinq indicateurs, donc rien d'autre ne
      // bouge à l'écran que sa disparition (US2-AC6).
      toast.success("Résultat supprimé.");
      setConfirmation(false);
      // Le tableau et les cinq indicateurs sont calculés côté serveur (FR-015).
      router.refresh();
    } catch (erreur) {
      // Un autre administrateur est passé avant : on le dit en clair et on remet
      // la page à jour, la ligne cliquée n'ayant plus de raison d'être là.
      if (erreur instanceof ApiError && erreur.status === 404) {
        toast.error(DISPARU);
        setConfirmation(false);
        router.refresh();
        return;
      }
      // Tout le reste est un incident : la modale reste ouverte pour réessayer,
      // et le message technique ne remonte pas à l'écran.
      toast.error(ECHEC);
    }
  }

  function fermerLeRattachement() {
    setRattachementOuvert(false);
    setSaisie("");
    setDejaPorte(false);
  }

  async function rattacher(cible: AdminAthlete) {
    // Le serveur accepte ce cas et ne journalise rien (FR-014) ; l'écran le dit
    // du même ton — un constat, pas une erreur.
    if (cible.id === resultat.coureurId) {
      setDejaPorte(true);
      return;
    }
    setDejaPorte(false);
    try {
      await rattachement.mutateAsync({ participationId: resultat.id, athleteId: cible.id });
      toast.success(`Résultat rattaché à ${cible.prenom} ${cible.nom}.`);
      fermerLeRattachement();
      // Si ce résultat était le dernier de la fiche courante, le serveur vient de
      // la purger : le rafraîchissement fait alors basculer la page sur son état
      // « introuvable », que `notFound()` gère déjà (T049, FR-016).
      router.refresh();
    } catch (erreur) {
      if (erreur instanceof ApiError && erreur.status === 404) {
        toast.error(DISPARU);
        fermerLeRattachement();
        router.refresh();
        return;
      }
      toast.error(ECHEC_RATTACHEMENT);
    }
  }

  const quand = formatDate(resultat.date);
  // La date reprend le format de la colonne « Date » du tableau : la
  // confirmation se relit contre la ligne que l'opérateur vient de cliquer.
  const intitule = quand ? `« ${resultat.epreuve} — ${quand} »` : `« ${resultat.epreuve} »`;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", ...style }}>
      {peutSupprimer && (
        <Button
          variant="secondary"
          size="sm"
          icon={<Trash2 size={14} aria-hidden="true" />}
          onClick={() => setConfirmation(true)}
          // Vingt lignes portent le même intitulé visible : sans cette précision,
          // rien ne dirait lequel des vingt résultats part.
          aria-label={`Supprimer le résultat de « ${resultat.epreuve} »`}
        >
          Supprimer
        </Button>
      )}

      {peutRattacher && (
        <Button
          variant="secondary"
          size="sm"
          icon={<ArrowRightLeft size={14} aria-hidden="true" />}
          onClick={() => setRattachementOuvert(true)}
          aria-label={`Rattacher le résultat de « ${resultat.epreuve} »`}
        >
          Rattacher
        </Button>
      )}

      {confirmation && (
        <Modal
          eyebrow="Résultat"
          title="Supprimer ce résultat ?"
          onClose={() => (suppression.isPending ? null : setConfirmation(false))}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button
                variant="ghost"
                onClick={() => setConfirmation(false)}
                disabled={suppression.isPending}
              >
                Annuler
              </Button>
              <Button onClick={supprimer} disabled={suppression.isPending}>
                {suppression.isPending ? "Suppression…" : "Supprimer"}
              </Button>
            </div>
          }
        >
          <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--tcn-text-body)", margin: 0 }}>
            {intitule} sera définitivement retiré de la fiche de {resultat.coureur}. Cette action
            est <strong>irréversible</strong>.
          </p>
        </Modal>
      )}

      {rattachementOuvert && (
        <Modal
          eyebrow="Résultat"
          title="Rattacher ce résultat"
          onClose={() => (rattachement.isPending ? null : fermerLeRattachement())}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button
                variant="ghost"
                onClick={fermerLeRattachement}
                disabled={rattachement.isPending}
              >
                Fermer
              </Button>
            </div>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--tcn-text-body)", margin: 0 }}>
              {intitule} quittera la fiche de {resultat.coureur} pour celle du coureur choisi. Le
              rattachement est <strong>irréversible</strong> ; si cette fiche n&apos;a plus aucun
              résultat, elle sera supprimée.
            </p>

            <div>
              <label
                htmlFor={`rattachement-${resultat.id}`}
                style={{
                  display: "block",
                  marginBottom: 6,
                  fontSize: 13,
                  fontWeight: 700,
                  color: "var(--tcn-text-muted)",
                }}
              >
                Rattacher à
              </label>
              <Input
                id={`rattachement-${resultat.id}`}
                type="search"
                value={saisie}
                onChange={(e) => setSaisie(e.target.value)}
                placeholder="Chercher un coureur par nom ou prénom…"
                autoComplete="off"
                disabled={rattachement.isPending}
              />
            </div>

            {dejaPorte && (
              <p
                role="status"
                style={{ fontSize: 13, color: "var(--tcn-text-muted)", margin: 0 }}
              >
                {DEJA_PORTE}
              </p>
            )}

            {candidats.isFetching && (
              <p style={{ fontSize: 13, color: "var(--tcn-text-faint)", margin: 0 }}>Recherche…</p>
            )}

            {candidats.data?.length === 0 && (
              <p style={{ fontSize: 13, color: "var(--tcn-text-faint)", margin: 0 }}>
                Aucun coureur ne correspond à cette recherche.
              </p>
            )}

            {/* Le choix **est** la confirmation : on ne valide pas un geste dont
                on vient de désigner explicitement la destination. D'où l'absence
                de bouton « Rattacher » dans le pied de cette modale. */}
            {candidats.data && candidats.data.length > 0 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  maxHeight: 260,
                  overflowY: "auto",
                }}
              >
                {candidats.data.map((candidat) => (
                  <button
                    key={candidat.id}
                    type="button"
                    className="tcn-rowlink"
                    onClick={() => rattacher(candidat)}
                    disabled={rattachement.isPending}
                    style={{
                      textAlign: "left",
                      padding: "8px 12px",
                      minHeight: 44,
                      border: "1px solid var(--tcn-border)",
                      borderRadius: "var(--tcn-radius-md)",
                      background: "var(--tcn-surface)",
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>
                      {candidat.nom} {candidat.prenom}
                    </span>
                    {/* La date de naissance n'est pas de l'ornement : sur nom +
                        prénom + club, deux vrais homonymes du même club sont
                        indiscernables, et la fusion serait sans retour. */}
                    <span
                      style={{
                        display: "block",
                        fontSize: 12,
                        color: "var(--tcn-text-faint)",
                      }}
                    >
                      {candidat.birth_date
                        ? `Né(e) le ${formatDate(candidat.birth_date)}`
                        : "Date de naissance inconnue"}
                      {candidat.club ? ` · ${candidat.club}` : ""}
                      {` · ${candidat.participations} résultat${candidat.participations > 1 ? "s" : ""}`}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
