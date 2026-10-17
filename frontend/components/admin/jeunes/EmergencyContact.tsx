import { trouverTelephone } from "@/lib/utils/telephone";

/**
 * Au bord du bassin, un numéro se compose d'un geste plutôt que de se recopier
 * (#1290). Partagé entre la fiche du jeune et la carte de l'appel (#1405) ;
 * un contact vide ne rend rien, chaque écran décide de son repli.
 */
export function EmergencyContact({ text }: { text: string | null }) {
  if (!text) return null;
  const phone = trouverTelephone(text);
  if (!phone) return <>{text}</>;
  return (
    <>
      {text.slice(0, phone.debut)}
      <a
        href={phone.href}
        className="ph-no-capture tcn-cible-tactile inline-flex items-center font-semibold text-accent-ink underline underline-offset-2"
      >
        {text.slice(phone.debut, phone.fin)}
      </a>
      {text.slice(phone.fin)}
    </>
  );
}
