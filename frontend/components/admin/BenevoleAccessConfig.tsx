"use client";
import { SharedPasswordCard } from "./SharedPasswordCard";

/**
 * Gestion admin du mot de passe partagé de la page bénévoles (#271 →
 * `specs/20260815-173645-admin-mdp-benevoles/`).
 */
export function BenevoleAccessConfig() {
  return (
    <SharedPasswordCard
      kind="benevole"
      inputId="benevole-password"
      minLength={8}
      refus={{ sujet: "accès bénévoles", action: "gérer l'accès bénévoles" }}
      copy={{
        title: "Accès bénévoles",
        description: (
          <>
            Mot de passe partagé de la page de vérification des résultats par
            les bénévoles. Il est stocké haché et salé : personne, y compris un
            administrateur, ne peut le retrouver une fois enregistré — seul un
            remplacement ou une nouvelle génération y change quelque chose.
          </>
        ),
        label: "Nouveau mot de passe",
        placeholder: "Saisir un nouveau mot de passe",
        generateLabel: "Générer un mot de passe sécurisé",
        generatedWarning: "Ce mot de passe ne sera plus jamais affiché — copiez-le maintenant.",
        replacedToast: "Mot de passe bénévoles remplacé.",
        generatedToast: "Mot de passe généré — transmettez-le aux bénévoles hors-bande.",
        dialogTitle: "Remplacer le mot de passe bénévoles ?",
        dialogDescription: (
          <>
            Toutes les sessions bénévoles déjà ouvertes cesseront
            immédiatement d&apos;être valides, l&apos;ancien mot de passe
            compris. Assurez-vous d&apos;avoir un moyen de transmettre le
            nouveau aux bénévoles.
          </>
        ),
      }}
    />
  );
}
