"use client";
import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Alert, Button, Input, Modal } from "@/components/tcn";
import { useAdminAthlete, useUpdateAthlete } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import type { AdminAthleteUpdate } from "@/lib/types";

export type CoureurACorriger = {
  id: number;
  nom: string;
  prenom: string;
  club: string | null;
};

/** Champ étiqueté du formulaire — `htmlFor` sur l'`<input>` que rend `tcn/Input`. */
function Champ({ id, label, children }: { id: string; label: string; children: ReactNode }) {
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
      // Affiché **dans** la modale plutôt qu'en toast : le refus le plus
      // fréquent est le conflit d'identité, et il se corrige dans le champ juste
      // au-dessus. La saisie n'est jamais vidée (FR-010).
      setRefus((erreur as Error).message);
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
              <Champ id="correction-naissance" label="Date de naissance">
                <Input
                  id="correction-naissance"
                  type="date"
                  value={naissance}
                  onChange={(e) => setNaissanceSaisie(e.target.value)}
                />
              </Champ>
            )}

            <Champ id="correction-club" label="Club actuel">
              <Input
                id="correction-club"
                value={club}
                onChange={(e) => setClub(e.target.value)}
                // Le champ vide est un état légitime, et c'est le seul moment où
                // il faut le dire : laisser le champ vide retire le club.
                placeholder="Sans club"
                autoComplete="off"
              />
            </Champ>
          </div>
        </Modal>
      )}
    </>
  );
}
