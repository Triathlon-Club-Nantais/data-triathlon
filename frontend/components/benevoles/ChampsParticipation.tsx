"use client";

import { Input } from "@/components/tcn";
import { brouillonDepuis, type Brouillon } from "@/lib/benevoles/brouillon";
import type { Participation } from "@/lib/types";

/** Les cinq champs du brouillon, dans l'ordre de lecture du panneau. */
const CHAMPS = [
  { cle: "nom_epreuve", id: "benevole-nom-epreuve", label: "Nom de l'épreuve", pleineLargeur: true },
  { cle: "bib_number", id: "benevole-dossard", label: "Dossard" },
  { cle: "rank_overall", id: "benevole-place", label: "Place au général", type: "number" },
  { cle: "club", id: "benevole-club", label: "Club" },
  { cle: "category", id: "benevole-categorie", label: "Catégorie" },
] as const satisfies ReadonlyArray<{
  cle: keyof Omit<Brouillon, "athlete_cible">;
  id: string;
  label: string;
  type?: string;
  pleineLargeur?: boolean;
}>;

/**
 * Les champs éditables du panneau bénévole, avec la **valeur d'origine à côté
 * des seuls champs modifiés** (#490, PROF-10).
 *
 * Purement présentationnel : il ne sait ni enregistrer ni valider. La
 * `Participation` complète est déjà en mémoire, donc la comparaison ne coûte
 * aucun appel.
 */
export function ChampsParticipation({
  brouillon,
  origine,
  onChange,
  disabled,
}: {
  brouillon: Brouillon;
  origine: Participation;
  onChange: (patch: Partial<Brouillon>) => void;
  disabled?: boolean;
}) {
  const valeursOrigine = brouillonDepuis(origine);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
      {CHAMPS.map(({ cle, id, label, ...reste }) => {
        const modifie = brouillon[cle].trim() !== valeursOrigine[cle].trim();
        const type = "type" in reste ? reste.type : undefined;
        return (
          <div
            key={cle}
            style={"pleineLargeur" in reste && reste.pleineLargeur ? { gridColumn: "1 / -1" } : undefined}
          >
            <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              {label}
            </label>
            <Input
              id={id}
              type={type}
              value={brouillon[cle]}
              disabled={disabled}
              onChange={(e) => onChange({ [cle]: e.target.value } as Partial<Brouillon>)}
              style={{ width: "100%" }}
            />
            {/* Ligne toujours montée, comme le verdict de `ProviderDetector`
                (#492) : sans quoi son insertion au premier caractère saisi
                pousse les quatre champs suivants et la barre d'action collante
                sous le clavier logiciel, pendant que le bénévole tape (#490,
                revue UI/UX, item 8). `minHeight` seul, pas de `visibility`
                — le texte doit disparaître du DOM une fois le champ revenu à
                sa valeur d'origine, seule la place reste. */}
            <div style={{ fontSize: 12, color: "var(--tcn-text-faint)", marginTop: 4, minHeight: 16 }}>
              {modifie && <>Valeur d&apos;origine : {valeursOrigine[cle].trim() || "vide"}</>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
