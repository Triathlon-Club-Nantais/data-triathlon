import { ContactEmail, InternalLink, List } from "../blocks";
import type { LegalDocument } from "../types";

export const TERMS_OF_USE: LegalDocument = {
  title: "Conditions d'utilisation",
  description: "Les règles d'usage du site des résultats du Triathlon Club Nantais.",
  updatedAt: "2026-10-01",
  sections: [
    {
      id: "objet",
      title: "Objet du site",
      content: (
        <p>
          Ce site rassemble les résultats de compétition des adhérents du Triathlon Club Nantais : il leur permet
          de retrouver leurs épreuves, de se situer dans les classements et de suivre la vie sportive du club. Il
          est gratuit, sans publicité, et entretenu par des bénévoles.
        </p>
      ),
    },
    {
      id: "acces",
      title: "Accès au site",
      content: (
        <p>
          Le site est réservé aux adhérents du club, qui reçoivent un code d&apos;accès. Ce code est propre au
          club : merci de ne pas le diffuser hors de celui-ci. Les présentes conditions, les mentions légales et
          la politique de confidentialité restent lisibles sans code. Le back-office est réservé aux bénévoles et
          administrateurs habilités.
        </p>
      ),
    },
    {
      id: "saisie-manuelle",
      title: "Saisie manuelle d'un résultat",
      content: (
        <>
          <p>
            Quand aucun chronométreur ne publie un résultat, un adhérent peut le saisir lui-même. En le faisant,
            vous vous engagez à déclarer :
          </p>
          <List>
            <li>un résultat réellement obtenu, le vôtre ou celui d&apos;un membre du club qui vous l&apos;a demandé ;</li>
            <li>des informations exactes : épreuve, date, temps, place et statut ;</li>
            <li>un lien vers une preuve (classement en ligne, page de l&apos;organisateur) quand il en existe une.</li>
          </List>
          <p>
            Un résultat saisi reste invisible tant qu&apos;un bénévole ne l&apos;a pas vérifié et validé. Le club
            peut refuser ou retirer une saisie inexacte.
          </p>
        </>
      ),
    },
    {
      id: "signalements",
      title: "Signalements",
      content: (
        <p>
          Le bouton de signalement présent sur chaque page sert à remonter un problème ou une suggestion. Décrivez
          ce que vous avez constaté sans y inscrire de données personnelles inutiles (adresse, téléphone, données
          de santé) : le message est lu par les bénévoles qui entretiennent le site.
        </p>
      ),
    },
    {
      id: "responsabilite",
      title: "Limites de responsabilité",
      content: (
        <p>
          Les résultats proviennent des chronométreurs des épreuves et sont repris tels qu&apos;ils les publient.
          Le club ne peut garantir leur exactitude ni leur exhaustivité : une erreur de la source, un athlète mal
          identifié ou une épreuve incomplète restent possibles. Le classement officiel d&apos;une épreuve est
          celui de son organisateur. Le site peut être momentanément indisponible, notamment pendant ses mises à
          jour.
        </p>
      ),
    },
    {
      id: "correction",
      title: "Demander une correction ou un retrait",
      content: (
        <p>
          Un résultat erroné se signale par le bouton de signalement ou à <ContactEmail />. Pour faire retirer vos
          résultats du site, la démarche est décrite dans la{" "}
          <InternalLink href="/confidentialite">politique de confidentialité</InternalLink>.
        </p>
      ),
    },
  ],
};
