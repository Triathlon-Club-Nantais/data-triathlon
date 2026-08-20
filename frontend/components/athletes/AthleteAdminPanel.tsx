"use client";
import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Alert, Button, Input, Modal } from "@/components/tcn";
import { ApiError } from "@/lib/api/client";
import { useAdminAthlete, useUpdateAthlete } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import type { AdminAthleteUpdate } from "@/lib/types";

export type CoureurACorriger = {
  id: number;
  nom: string;
  prenom: string;
  club: string | null;
};

/** Un `404` décrit une requête ; l'opérateur, lui, voit un écran (FR-016). */
const DISPARU = "Ce coureur n'existe plus. La page a été mise à jour.";
/** Refus prononcé ici plutôt qu'au serveur, dont le message est en anglais. */
const IDENTITE_INCOMPLETE = "Le nom et le prénom ne peuvent pas être vides.";
const ECHEC = "La correction n'a pas abouti. Réessayez dans un instant.";
const NAISSANCE_ILLISIBLE =
  "La date de naissance n'a pas pu être lue : elle n'est pas modifiable pour l'instant.";

/**
 * Champ étiqueté du formulaire — `htmlFor` sur l'`<input>` que rend `tcn/Input`.
 *
 * `aide` est un texte **permanent** sous le champ, jamais un `placeholder` : une
 * instruction qui disparaît à la première frappe manque précisément le moment où
 * elle sert. Elle est rattachée au champ par `aria-describedby`, que l'appelant
 * pose lui-même sur l'`<input>` — `tcn/Input` relaie tous ses attributs.
 */
function Champ({
  id,
  label,
  aide,
  children,
}: {
  id: string;
  label: string;
  aide?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        style={{
          display: "block",
          marginBottom: 6,
          fontSize: 13,
          fontWeight: 700,
          color: "var(--tcn-text-muted)",
        }}
      >
        {label}
      </label>
      {children}
      {aide ? (
        <p
          id={`${id}-aide`}
          style={{ margin: "6px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}
        >
          {aide}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Corrections de la fiche d'un coureur, depuis sa page publique (#439).
 *
 * La visibilité se décide **dans le navigateur**, pouvoir par pouvoir : la page
 * reste rendue par `apiServer.getAthlete` (sans cookies) pour que le visiteur
 * anonyme ne paie rien de plus, et `useSession` ne déclenche même pas d'appel
 * réseau tant que le cookie témoin `tcn_logged_in` est absent (SC-004).
 *
 * Il n'existe aucun échelon « administrateur » : porter `athletes:write` donne
 * exactement ces corrections, et rien d'autre. Une session **illisible** n'est
 * pas une session sans pouvoirs, mais l'écran n'affirme ni l'un ni l'autre — il
 * n'offre rien (FR-008).
 */
export function AthleteAdminPanel({ athlete }: { athlete: CoureurACorriger }) {
  const session = useSession();
  const peutCorriger = session.data?.permissions.includes("athletes:write") ?? false;
  const peutLireLaFiche = session.data?.permissions.includes("athletes:read") ?? false;

  const [ouverte, setOuverte] = useState(false);
  const [nom, setNom] = useState(athlete.nom);
  const [prenom, setPrenom] = useState(athlete.prenom);
  // Le club, lui, voyage sur la ressource **publique** : il est prérempli sans
  // rien lire de gardé, donc sans attendre `athletes:read` (#439).
  const [club, setClub] = useState(athlete.club ?? "");
  // `null` = pas encore touchée : la valeur affichée reste celle de la fiche
  // gardée, qui arrive après l'ouverture. Un `useEffect` de recopie écraserait
  // une saisie faite entre-temps.
  const [naissanceSaisie, setNaissanceSaisie] = useState<string | null>(null);
  const [refus, setRefus] = useState<string | null>(null);

  const router = useRouter();
  const correction = useUpdateAthlete();
  // La date de naissance ne vit que sur la ressource gardée par `athletes:read`
  // (un résultat n'en porte pas) : sans ce pouvoir, on ne la lit pas, donc on ne
  // l'offre pas et on ne l'envoie pas (D7).
  const fiche = useAdminAthlete(ouverte && peutLireLaFiche ? athlete.id : null);

  if (!peutCorriger) return null;

  const nomComplet = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");
  const naissanceEnBase = fiche.data?.birth_date ?? "";
  const naissance = naissanceSaisie ?? naissanceEnBase;

  function ouvrir() {
    setNom(athlete.nom);
    setPrenom(athlete.prenom);
    setClub(athlete.club ?? "");
    setNaissanceSaisie(null);
    setRefus(null);
    setOuverte(true);
  }

  async function enregistrer() {
    // Seuls les champs **corrigés** partent : ce qui est absent du corps n'est
    // pas réécrit (`exclude_unset` côté serveur), ce qui vaut garantie de
    // non-effacement pour la date de naissance qu'on n'a pas lue.
    // « Un nom vide n'est pas une correction » (spec, cas limites) : le serveur
    // le refuse aussi, mais avec le message anglais de Pydantic — le refus se
    // prononce donc ici, en français et sans aller-retour.
    if (nom.trim() === "" || prenom.trim() === "") {
      setRefus(IDENTITE_INCOMPLETE);
      return;
    }

    const champs: Partial<AdminAthleteUpdate> = {};
    if (nom !== athlete.nom) champs.nom = nom;
    if (prenom !== athlete.prenom) champs.prenom = prenom;
    if (peutLireLaFiche && naissance !== naissanceEnBase) {
      champs.birth_date = naissance === "" ? null : naissance;
    }
    // Champ vidé → `null`, jamais `""` : « sans club » est une valeur, la chaîne
    // vide serait rangée comme un libellé de club à part entière (US3-AC2). Et un
    // club renvoyé à l'identique poserait le verrou sans qu'aucune correction ait
    // eu lieu, gelant le libellé contre tous les imports à venir.
    if (club !== (athlete.club ?? "")) champs.club = club === "" ? null : club;
    if (Object.keys(champs).length === 0) {
      setOuverte(false);
      return;
    }

    try {
      await correction.mutateAsync({ id: athlete.id, champs });
      toast.success("Fiche corrigée.");
      setOuverte(false);
      // Le nom en tête et les cinq indicateurs sont calculés côté serveur : une
      // mise à jour d'état local ne les recalculerait pas (FR-015).
      router.refresh();
    } catch (erreur) {
      // La fiche a disparu sous les doigts — un rattachement concurrent a pu
      // emporter son dernier résultat, donc la fiche. Il n'y a plus rien à
      // corriger ici : c'est la page qu'il faut remettre à jour (FR-016).
      if (erreur instanceof ApiError && erreur.status === 404) {
        toast.error(DISPARU);
        setOuverte(false);
        router.refresh();
        return;
      }
      // Affiché **dans** la modale plutôt qu'en toast : le refus le plus
      // fréquent est le conflit d'identité, et il se corrige dans le champ juste
      // au-dessus. La saisie n'est jamais vidée (FR-010). Seul le 409 porte un
      // message écrit pour l'opérateur ; tout le reste est un incident, dont le
      // texte serveur serait technique et anglais (FR-017).
      const conflit = erreur instanceof ApiError && erreur.status === 409;
      setRefus(conflit ? erreur.message : ECHEC);
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={ouvrir} aria-label={`Corriger la fiche de ${nomComplet}`}>
        Corriger la fiche
      </Button>

      {ouverte && (
        <Modal
          eyebrow="Fiche du coureur"
          title="Corriger la fiche"
          onClose={() => (correction.isPending ? null : setOuverte(false))}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button variant="ghost" onClick={() => setOuverte(false)} disabled={correction.isPending}>
                Annuler
              </Button>
              <Button onClick={enregistrer} disabled={correction.isPending}>
                {correction.isPending ? "Enregistrement…" : "Enregistrer"}
              </Button>
            </div>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {refus && (
              <div role="alert">
                <Alert status="error" title="Correction refusée">
                  {refus}
                </Alert>
              </div>
            )}

            <Champ id="correction-nom" label="Nom">
              <Input
                id="correction-nom"
                value={nom}
                onChange={(e) => setNom(e.target.value)}
                autoComplete="off"
              />
            </Champ>

            <Champ id="correction-prenom" label="Prénom">
              <Input
                id="correction-prenom"
                value={prenom}
                onChange={(e) => setPrenom(e.target.value)}
                autoComplete="off"
              />
            </Champ>

            {peutLireLaFiche && (
              // Un champ date vide se lit « ce coureur n'a pas de date de
              // naissance ». Tant que la fiche gardée n'est pas arrivée — ou si
              // sa lecture échoue — c'est faux, et le dire coûte une ligne.
              <Champ
                id="correction-naissance"
                label="Date de naissance"
                aide={
                  fiche.isError
                    ? NAISSANCE_ILLISIBLE
                    : fiche.isPending
                      ? "Lecture de la date de naissance…"
                      : undefined
                }
              >
                <Input
                  id="correction-naissance"
                  type="date"
                  value={naissance}
                  onChange={(e) => setNaissanceSaisie(e.target.value)}
                  disabled={fiche.isError || fiche.isPending}
                  aria-describedby={
                    fiche.isError || fiche.isPending ? "correction-naissance-aide" : undefined
                  }
                />
              </Champ>
            )}

            <Champ
              id="correction-club"
              label="Club actuel"
              // Le champ vide est un état légitime, et c'est le seul moment où
              // il faut le dire. En `placeholder`, l'instruction disparaissait à
              // la première frappe — juste avant le geste qu'elle décrit.
              aide="Laisser le champ vide retire le club."
            >
              <Input
                id="correction-club"
                value={club}
                onChange={(e) => setClub(e.target.value)}
                aria-describedby="correction-club-aide"
                autoComplete="off"
              />
            </Champ>
          </div>
        </Modal>
      )}
    </>
  );
}
