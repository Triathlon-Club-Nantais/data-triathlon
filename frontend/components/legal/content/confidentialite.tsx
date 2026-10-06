import { AnalyticsConsentSettings } from "@/components/analytics/AnalyticsConsent";
import { ANALYTICS_CONSENT_KEY, RETOUR_CONNEXION_KEY } from "@/lib/constants";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";
import { ContactEmail, ExternalLink, InternalLink, List, Table } from "../blocks";
import type { LegalDocument } from "../types";

// Faits juridiques : docs/superpowers/specs/2026-10-01-base-legale-decision.md (#332), qui prime.
// Les noms des cookies posés par l'API sont tenus contre leurs constantes par backend/tests/test_legal_privacy_policy.py.
export const PRIVACY_POLICY: LegalDocument = {
  title: "Politique de confidentialité",
  description:
    "Ce que le Triathlon Club Nantais fait des données de ce site, pourquoi, combien de temps, et comment faire valoir vos droits.",
  updatedAt: "2026-10-06",
  sections: [
    {
      id: "responsable",
      title: "Le responsable du traitement",
      content: (
        <>
          <p>
            Les données de ce site sont traitées par l&apos;association <strong>Triathlon Club Nantais</strong>,
            2 boulevard René Coty, 44100 Nantes, représentée par son président.
          </p>
          <p>
            Pour toute question sur vos données : <ContactEmail />.
          </p>
        </>
      ),
    },
    {
      id: "donnees",
      title: "Les données traitées et leur provenance",
      content: (
        <>
          <p>
            <strong>Les résultats d&apos;épreuves.</strong> Pour chaque athlète classé dans une épreuve importée,
            membre du club ou non : nom, prénom, sexe, catégorie d&apos;âge, club déclaré, numéro de dossard, temps
            total et temps intermédiaires, classements (général, par catégorie, par sexe), statut (arrivé, abandon…)
            et, pour un relais, le nom de l&apos;équipe. La ligne du classement telle que la source l&apos;a publiée
            est conservée avec le résultat. La date de naissance, quand la source la donne, n&apos;est visible que
            des administrateurs.
          </p>
          <p>Ces résultats proviennent de deux sources :</p>
          <List>
            <li>
              les sites des chronométreurs, où ils sont déjà publiés : Klikego, Breizh Chrono, TimePulse,
              Sportinnovation, ProLiveSport, Chronoplace, Wiclax (G-Live), RaceResult, T2Area (Fédération Française
              de Triathlon), Competitor (Ironman), ok-time, runnerbreizh, Sporthive (MYLAPS) et chronoweb. Le lien
              d&apos;une épreuve est collé par un adhérent, ou fourni par un administrateur dans une liste de liens ;
            </li>
            <li>
              la saisie manuelle, par un adhérent, d&apos;un résultat qu&apos;aucun chronométreur ne publie, avec un
              lien de preuve quand il existe. Elle reste invisible tant qu&apos;un bénévole ne l&apos;a pas validée.
            </li>
          </List>
          <p>
            Les épreuves et catégories jeunes, jusqu&apos;à minime inclus, ne sont pas importées depuis les
            chronométreurs.
          </p>
          <p>
            <strong>La liste des licenciés du club.</strong> Nom, prénom, sexe et numéro de licence des adhérents
            licenciés au club, saison par saison. Elle est relue chaque semaine sur la page publique du club de la
            Fédération Française de Triathlon (T2Area), ou importée par un administrateur pour une saison passée.
            Elle sert à reconnaître comme résultats du club ceux de ses licenciés, quand le chronométreur ne publie
            pas leur club, et à distinguer la fiche d&apos;un licencié de celle d&apos;un homonyme, à l&apos;import
            des résultats comme lors de la revue des fiches. Seuls les administrateurs habilités la consultent.
          </p>
          <p>
            <strong>Les comptes du back-office.</strong> Les bénévoles et administrateurs se connectent avec leur
            compte GitHub : le site en reçoit l&apos;adresse électronique, le nom affiché et l&apos;identifiant
            GitHub. Un compte peut être rattaché à la fiche athlète de son titulaire. Le site garde la trace des
            actions d&apos;administration.
          </p>
          <p>
            <strong>Les signalements.</strong> Quand vous signalez un problème depuis le site : votre message, la
            page concernée, votre navigateur, votre adresse IP et, si vous êtes connecté au back-office, votre
            compte. L&apos;adresse IP sert uniquement à limiter le nombre d&apos;envois ; elle n&apos;est jamais
            affichée.
          </p>
          <p>
            <strong>L&apos;école de triathlon.</strong> Pour les jeunes licenciés encadrés par le club : identité,
            date de naissance, contact d&apos;urgence, notes des encadrants et présence aux séances. Ces données ne
            sont visibles que des encadrants habilités.
          </p>
          <p>
            <strong>La mesure d&apos;audience.</strong> Par défaut, le site compte les pages consultées, quelques
            actions choisies (filtres, imports d&apos;épreuves, connexion) et les erreurs rencontrées,{" "}
            <strong>sans cookie</strong> et sans vous suivre d&apos;un jour à l&apos;autre : le prestataire de
            mesure ne reçoit qu&apos;un identifiant calculé à partir de votre adresse IP et de votre navigateur,
            renouvelé chaque jour. Si vous acceptez la mesure détaillée, il reçoit aussi vos interactions avec les
            pages (clics) et dépose des cookies ; pour un utilisateur connecté au back-office, la mesure est alors
            rattachée à son compte : son adresse électronique, son nom affiché et ses rôles lui sont transmis.
            Retirer ensuite votre accord arrête cette mesure détaillée, sans effacer ce qui a déjà été transmis :
            pour cela, exercez votre droit à l&apos;effacement (voir « Vos droits »). Les actions faites dans le
            back-office sont comptées par le serveur du site, rattachées à l&apos;identifiant du compte (voir
            « Cookies et stockage du navigateur »).
          </p>
        </>
      ),
    },
    {
      id: "finalite",
      title: "Pourquoi, et sur quelle base légale",
      content: (
        <>
          <p>
            Le site permet aux adhérents de suivre leurs résultats et ceux du club, de se situer dans le classement
            complet de chaque épreuve, et d&apos;animer la vie du club (saisons, bénévolat). Sans les autres
            participants, la place d&apos;un adhérent dans une épreuve n&apos;aurait pas de sens : c&apos;est pourquoi
            le classement complet est conservé.
          </p>
          <p>
            Ce traitement repose sur l&apos;<strong>intérêt légitime</strong> du club (article 6.1.f du règlement
            général sur la protection des données, le RGPD). Cela signifie que le club n&apos;a pas besoin de votre
            accord préalable, mais qu&apos;il doit vous informer, limiter ce qu&apos;il fait de vos données, et
            respecter votre droit de vous y opposer. Le club estime que vos intérêts ne prévalent pas sur le sien,
            pour cinq raisons :
          </p>
          <List>
            <li>ces résultats ont déjà été rendus publics par le chronométreur, dans le même but ;</li>
            <li>la liste des licenciés est déjà publiée par la fédération, et ne sert qu&apos;à compter ;</li>
            <li>
              le site est réservé aux adhérents, par un code d&apos;accès, et il est exclu des moteurs de recherche ;
            </li>
            <li>les résultats des jeunes ne sont pas importés depuis les chronométreurs ;</li>
            <li>aucune donnée n&apos;est vendue, cédée ni utilisée à des fins commerciales.</li>
          </List>
          <p>
            Les données de l&apos;école de triathlon reposent, elles, sur l&apos;adhésion au club (article 6.1.b du
            RGPD : ce qui est nécessaire à l&apos;exécution du contrat d&apos;adhésion) et sur la sécurité des jeunes
            encadrés. Les comptes du back-office et les signalements reposent sur l&apos;intérêt légitime du club à
            administrer son site.
          </p>
        </>
      ),
    },
    {
      id: "conservation",
      title: "Combien de temps elles sont conservées",
      content: (
        <Table
          label="Durées de conservation"
          head={["Données", "Durée"]}
          rows={[
            ["Résultats d'épreuves", "Tant que le service existe (archive sportive du club), sauf opposition de votre part"],
            [
              "Liste des licenciés du club",
              "La saison en cours et la précédente ; ensuite, seuls sont gardés la saison et le rattachement à la fiche de résultats (le numéro de licence et le sexe sont effacés, le nom est celui de la fiche)",
            ],
            ["Signalements, adresse IP comprise", "12 mois après leur envoi"],
            ["Journal des actions d'administration", "12 mois"],
            ["Compte du back-office", "Tant que son titulaire est autorisé à se connecter"],
            ["Session de connexion au back-office", "7 jours"],
            ["Mémorisation du code d'accès au site", "90 jours"],
            ["École de triathlon", "Durée de l'adhésion, plus une saison"],
          ]}
        />
      ),
    },
    {
      id: "destinataires",
      title: "Qui y a accès",
      content: (
        <>
          <p>
            Les résultats sont consultables par les adhérents du club, qui disposent du code d&apos;accès. Les
            saisies en attente, les dates de naissance et les signalements ne sont visibles que des bénévoles
            (adhérents ou non) et administrateurs habilités ; la liste des licenciés, que des administrateurs
            habilités ; les données de l&apos;école de triathlon, que des
            encadrants.
          </p>
          <p>Le club s&apos;appuie sur des prestataires techniques, qui n&apos;agissent que pour son compte :</p>
          <Table
            label="Prestataires techniques"
            head={["Prestataire", "Rôle", "Lieu des données"]}
            rows={[
              ["Vercel Inc.", "Hébergement du site", "États-Unis"],
              ["Render Services, Inc.", "Hébergement du serveur de données", "Francfort (Allemagne)"],
              ["Microsoft Ireland Operations Ltd (Azure)", "Base de données", "France"],
              ["Supabase Inc.", "Base de données de test, avant mise en ligne", "Non précisé par le prestataire"],
              ["GitHub, Inc.", "Connexion au back-office, mises à jour planifiées des résultats", "États-Unis"],
              ["PostHog Inc.", "Mesure d'audience", "Union européenne"],
            ]}
          />
          <p>
            Certaines données sont donc traitées hors de l&apos;Union européenne, aux États-Unis. Ces transferts sont
            encadrés, selon le prestataire, par le cadre de protection des données entre l&apos;Union européenne et
            les États-Unis ou par les clauses contractuelles types de la Commission européenne.
          </p>
        </>
      ),
    },
    {
      id: "droits",
      title: "Vos droits et comment les exercer",
      content: (
        <>
          <p>Vous pouvez, à tout moment :</p>
          <List>
            <li>
              <strong>vous opposer</strong> à la présence de vos résultats sur le site, sauf motif impérieux que le
              club devra vous exposer : ils sont alors rendus anonymes (le temps et le rang restent dans le
              classement, sans votre nom, votre club ni votre catégorie) et votre fiche est supprimée. Pour que
              les imports suivants ne vous fassent pas réapparaître, le site garde une empreinte de votre nom et
              de votre prénom, jamais le nom lui-même ; les résultats publiés ensuite à ce nom arrivent anonymes.
              Vous êtes aussi retiré de la liste des licenciés du club, et ses relectures suivantes vous en écartent ;
            </li>
            <li>
              <strong>accéder</strong> aux données qui vous concernent et en obtenir une copie ;
            </li>
            <li>
              <strong>faire rectifier</strong> une donnée inexacte (un nom mal orthographié, un club erroné) ;
            </li>
            <li>
              <strong>demander l&apos;effacement</strong> de vos données, ou la <strong>limitation</strong> de leur
              utilisation le temps d&apos;examiner une contestation.
            </li>
          </List>
          <p>
            Pour cela, ouvrez le bouton rond de signalement (💬) en bas à droite de chaque page et choisissez
            « Retrait de mes données »,
            écrivez à <ContactEmail />, ou par courrier à Triathlon Club Nantais, 2 boulevard René Coty,
            44100 Nantes. Indiquez votre nom et votre prénom tels qu&apos;ils figurent dans les classements, et
            l&apos;épreuve concernée (nom et date) : cela suffit à retrouver vos résultats. Le club vous répond dans
            un délai d&apos;un mois.
          </p>
        </>
      ),
    },
    {
      id: "cnil",
      title: "Réclamation auprès de la CNIL",
      content: (
        <p>
          Si vous estimez que vos droits ne sont pas respectés, vous pouvez adresser une réclamation à la Commission
          nationale de l&apos;informatique et des libertés (CNIL), en ligne sur{" "}
          <ExternalLink href="https://www.cnil.fr/fr/plaintes">cnil.fr/fr/plaintes</ExternalLink> ou par courrier :
          CNIL, 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07.
        </p>
      ),
    },
    {
      id: "cookies",
      title: "Cookies et stockage du navigateur",
      content: (
        <>
          <p>Le site dépose ou lit dans votre navigateur :</p>
          <Table
            label="Cookies et stockage du navigateur"
            head={["Nom", "Type", "À quoi il sert", "Durée"]}
            rows={[
              ["tcn_site_session", "cookie", "Mémoriser que vous avez saisi le code d'accès", "90 jours"],
              ["tcn_session", "cookie", "Maintenir votre connexion au back-office", "7 jours"],
              ["tcn_logged_in", "cookie", "Savoir qu'une connexion au back-office est ouverte", "7 jours au plus"],
              ["tcn_auth_state", "cookie", "Sécuriser la connexion par GitHub", "10 minutes"],
              ["tcn_benevole_session", "cookie", "Mémoriser l'accès à l'espace bénévoles", "Jusqu'à la fermeture du navigateur"],
              [NAV_WIDTH_COOKIE, "cookie", "Retenir si le menu est déplié", "1 an"],
              ["tcn-athlete", "stockage local", "Retenir l'athlète que vous avez choisi comme « moi »", "Jusqu'à ce que vous le changiez"],
              [RETOUR_CONNEXION_KEY, "stockage de session", "Vous ramener à la bonne page après la connexion", "Jusqu'à la fermeture de l'onglet"],
              [ANALYTICS_CONSENT_KEY, "stockage local", "Retenir votre choix sur la mesure d'audience détaillée", "Choix valable 6 mois"],
              ["__ph_opt_in_out_…", "stockage local", "Retenir votre choix côté PostHog, dès que vous acceptez ou refusez", "1 an"],
              ["ph_…", "cookie et stockage local", "Mesure d'audience détaillée (PostHog), seulement si vous l'acceptez", "1 an"],
            ]}
          />
          <p>
            Sur le site en ligne, les deux cookies de connexion au back-office portent le préfixe « __Host- »
            (par exemple « __Host-tcn_session »), qui interdit leur partage avec un autre site.
          </p>
          <p>
            Tous servent au fonctionnement du site ou à retenir votre choix, sauf les traceurs PostHog « ph_… »,
            qui ne sont déposés qu&apos;avec votre accord. Au bout de six mois, le site vous redemande votre choix.
            Vous pouvez aussi supprimer chacun de ces éléments depuis les réglages de votre navigateur ; supprimer
            ceux de connexion ou du code d&apos;accès vous demandera de vous reconnecter ou de saisir à nouveau le
            code.
          </p>
          <AnalyticsConsentSettings />
        </>
      ),
    },
    {
      id: "mises-a-jour",
      title: "Mises à jour de cette politique",
      content: (
        <p>
          Cette politique évolue avec le site ; sa date de dernière mise à jour figure en tête de page. Les règles
          d&apos;usage du site sont dans les{" "}
          <InternalLink href="/cgu">conditions d&apos;utilisation</InternalLink>.
        </p>
      ),
    },
  ],
};
