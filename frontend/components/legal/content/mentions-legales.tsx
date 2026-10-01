import { ContactEmail, ExternalLink, InternalLink } from "../blocks";
import type { LegalDocument } from "../types";

export const LEGAL_NOTICE: LegalDocument = {
  title: "Mentions légales",
  description: "Qui édite ce site, qui l'héberge, et comment joindre le club.",
  updatedAt: "2026-10-01",
  sections: [
    {
      id: "editeur",
      title: "Éditeur",
      content: (
        <p>
          Ce site est édité par l&apos;association <strong>Triathlon Club Nantais</strong>, dont le siège est au
          2 boulevard René Coty, 44100 Nantes (SIRET 403 516 347 00016).
          <br />
          Directeur de la publication : Aurélien Gantier, commission communication du club.
          <br />
          Contact : <ContactEmail />.
        </p>
      ),
    },
    {
      id: "hebergement",
      title: "Hébergement",
      content: (
        <ul className="space-y-3">
          <li>
            <strong>Site</strong> : Vercel Inc., 440 N Barranca Ave #4133, Covina, CA 91723, États-Unis.
          </li>
          <li>
            <strong>Serveur de données</strong> : Render Services, Inc., 525 Brannan Street, Suite 300, San
            Francisco, CA 94107, États-Unis (serveurs situés à Francfort, Allemagne).
          </li>
          <li>
            <strong>Base de données</strong> : Microsoft Ireland Operations Ltd (Microsoft Azure), One Microsoft
            Place, South County Business Park, Leopardstown, Dublin 18, Irlande (serveurs situés en France).
          </li>
        </ul>
      ),
    },
    {
      id: "contenus",
      title: "Contenus et code source",
      content: (
        <>
          <p>
            Les résultats affichés proviennent des chronométreurs des épreuves, dont la source est indiquée sur
            chaque résultat. Le site est développé par des bénévoles du club ; son code source est publié sous
            licence libre AGPL-3.0 sur{" "}
            <ExternalLink href="https://github.com/Triathlon-Club-Nantais/data-triathlon">GitHub</ExternalLink>.
          </p>
          <p>
            Le site du club est{" "}
            <ExternalLink href="https://triathlon-club-nantais.com/">triathlon-club-nantais.com</ExternalLink>.
          </p>
        </>
      ),
    },
    {
      id: "donnees-personnelles",
      title: "Données personnelles",
      content: (
        <p>
          Ce que le club fait de vos données, et comment faire retirer vos résultats, est décrit dans la{" "}
          <InternalLink href="/confidentialite">politique de confidentialité</InternalLink>.
        </p>
      ),
    },
  ],
};
