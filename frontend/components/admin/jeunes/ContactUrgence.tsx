import { trouverTelephone } from "@/lib/utils/telephone";

/**
 * Au bord du bassin, un numéro se compose d'un geste plutôt que de se recopier
 * (#1290). Partagé entre la fiche du jeune et la carte de l'appel (#1405) ;
 * un contact vide ne rend rien, chaque écran décide de son repli.
 */
export function ContactUrgence({ texte }: { texte: string | null }) {
  if (!texte) return null;
  const telephone = trouverTelephone(texte);
  if (!telephone) return <>{texte}</>;
  return (
    <>
      {texte.slice(0, telephone.debut)}
      <a
        href={telephone.href}
        className="ph-no-capture tcn-cible-tactile inline-flex items-center font-semibold text-accent-ink underline underline-offset-2"
      >
        {texte.slice(telephone.debut, telephone.fin)}
      </a>
      {texte.slice(telephone.fin)}
    </>
  );
}
