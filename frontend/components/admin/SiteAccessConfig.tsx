"use client";
import { SharedPasswordCard } from "./SharedPasswordCard";

/** Gestion admin du mot de passe partagé d'accès au site (#509). */
export function SiteAccessConfig() {
  return (
    <SharedPasswordCard
      kind="site"
      inputId="site-password"
      minLength={12}
      refus={{ sujet: "accès au site", action: "gérer l'accès au site" }}
      copy={{
        title: "Accès au site",
        description: (
          <>
            Code d&apos;accès du site, partagé et demandé à l&apos;entrée. Il est stocké
            haché et salé : personne, y compris un administrateur, ne peut le
            retrouver une fois enregistré — seul un remplacement ou une nouvelle
            génération y change quelque chose.
          </>
        ),
        label: "Nouveau code d'accès du site",
        placeholder: "Saisir un nouveau code d'accès du site",
        generateLabel: "Générer un code d'accès sécurisé",
        generatedWarning: "Ce code d'accès ne sera plus jamais affiché — copiez-le maintenant.",
        replacedToast: "Code d'accès du site remplacé.",
        generatedToast: "Code d'accès du site généré, transmettez-le par un autre canal.",
        dialogTitle: "Remplacer le code d'accès du site ?",
        dialogDescription: (
          <>
            Toutes les sessions ouvertes cesseront immédiatement d&apos;être
            valides, l&apos;ancien code compris. Assurez-vous d&apos;avoir
            un moyen de transmettre le nouveau.
          </>
        ),
      }}
      help={
        <>
          12 caractères minimum. Préférez « Générer un code d&apos;accès sécurisé »,
          plus difficile à deviner qu&apos;un code saisi.
        </>
      }
    />
  );
}
