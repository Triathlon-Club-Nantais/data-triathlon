import type { GuideSection } from "./types";

export const GUIDE_MEMBRE: GuideSection[] = [
  {
    id: "dashboard",
    titre: "Accueil et Mon espace",
    casUsage: "Prendre le pouls du club sur l'accueil, puis retrouver sa propre saison dans « Mon espace ».",
    etapes: [
      "Ouvrir « Accueil » depuis la navigation principale : la dernière sortie du club, puis un raccourci vers chaque espace.",
      "Voir la saison du club en chiffres et ses dernières épreuves, et changer de saison avec le sélecteur en haut de « Accueil ».",
      "Ouvrir « Mon espace » pour votre propre saison : son sélecteur de saison choisit la ou les saisons à afficher, et un filtre par discipline est disponible.",
    ],
    captures: [
      {
        src: "/guide/membre/accueil.jpg",
        alt: "Accueil du club : la dernière sortie, la saison en chiffres, les raccourcis vers chaque espace et le tableau des dernières épreuves",
      },
    ],
  },
  {
    id: "club",
    titre: "Espace club",
    casUsage: "Voir la synthèse du club : podiums, composition, et derniers résultats enregistrés.",
    etapes: [
      "Ouvrir « Espace club » depuis la navigation (section « Club »).",
      "Consulter la synthèse et les podiums, ou les onglets « Performance » et « Composition ».",
    ],
    captures: [{ src: "/guide/membre/club.jpg", alt: "Espace club, synthèse et podiums" }],
  },
  {
    id: "resultats",
    titre: "Résultats",
    casUsage: "Retrouver les épreuves du club et consulter le classement d'une épreuve précise.",
    etapes: [
      "Ouvrir « Résultats » depuis la navigation principale.",
      "Filtrer par saison, entre « Tous » et « Membres TCN », ou par recherche libre.",
      "Sélectionner une épreuve pour en voir le classement complet.",
    ],
    captures: [{ src: "/guide/membre/resultats.jpg", alt: "Liste des résultats avec filtres" }],
  },
  {
    id: "fiche-athlete",
    titre: "Fiche athlète",
    casUsage:
      "Retrouver un athlète, voir son historique et sa progression, et le choisir pour personnaliser « Mon espace ».",
    etapes: [
      "Ouvrir la recherche d'athlète avec la loupe de la navigation, ou le raccourci ⌘K (Mac) ou Ctrl K.",
      "Taper quelques lettres du nom, puis ouvrir la fiche.",
      "Cliquer sur « Choisir cet athlète » : un raccourci « Mes résultats » apparaît dans les filtres de « Résultats ». Pour retrouver votre saison dans « Mon espace », rattachez plutôt votre compte à votre fiche.",
    ],
    captures: [{ src: "/guide/membre/fiche-athlete.jpg", alt: "Fiche d'un athlète avec le bouton « Choisir cet athlète »" }],
  },
  {
    id: "comparaison",
    titre: "Comparaison",
    casUsage:
      "Situer son temps, segment par segment, par rapport aux positions de référence du classement scratch de la même épreuve.",
    etapes: [
      "Depuis « Résultats », ouvrir une épreuve puis une participation.",
      "Faire défiler jusqu'au tableau de comparaison, sur la fiche de la participation.",
    ],
    captures: [{ src: "/guide/membre/comparaison.jpg", alt: "Tableau de comparaison d'une participation" }],
  },
  {
    id: "ajouter",
    titre: "Ajouter une épreuve",
    casUsage: "Importer une épreuve manquante à partir de son lien de chronométrage.",
    etapes: [
      "Ouvrir « Ajouter une épreuve » depuis la navigation principale.",
      "Coller le lien de la page de résultats du chronométreur.",
      "Vérifier le fournisseur détecté, puis cliquer sur « Enregistrer les résultats ».",
    ],
    captures: [{ src: "/guide/membre/ajouter.jpg", alt: "Formulaire d'ajout d'une épreuve par URL" }],
  },
  {
    id: "benevolat",
    titre: "Bénévolat",
    // Masquée avec son écran derrière `pages:preview` (#879).
    destination: "/benevolat",
    casUsage: "Créditer un athlète du club pour une activité de bénévolat, comptée dans son quota de saison.",
    etapes: [
      "Ouvrir « Bénévolat » depuis la navigation (section « Club »).",
      "Rechercher l'athlète concerné, puis renseigner le titre et la description de l'activité, tous deux obligatoires.",
      "Envoyer la déclaration : elle est instruite par un administrateur avant de compter pour le quota.",
    ],
    captures: [{ src: "/guide/membre/benevolat.jpg", alt: "Formulaire de déclaration de bénévolat" }],
  },
  {
    id: "rattachement",
    titre: "Rattacher votre compte à votre fiche",
    casUsage: "Relier votre compte à votre fiche athlète pour accéder à « Mon espace » et à ses outils personnels.",
    etapes: [
      "Ouvrir la recherche d'athlète avec la loupe de la navigation, puis ouvrir votre fiche.",
      "Cliquer sur « C'est moi » : la demande part dans la file du club, jamais rattachée d'office.",
      "Attendre la validation du club : « Demande de rattachement en attente » s'affiche sur la fiche. Vous pouvez retirer la demande avec « Annuler la demande » depuis « Mon compte » (menu de votre compte).",
      "Une fois la demande validée, la fiche affiche « Votre fiche » et « Mon espace » s'ouvre.",
      "En cas de refus, une nouvelle demande reste possible depuis « Mon espace ». Pour vous détacher plus tard, utiliser « Me détacher de ma fiche » dans « Mon compte » : un nouveau rattachement demandera une nouvelle validation du club.",
    ],
    captures: [],
  },
  {
    id: "objectifs",
    titre: "Objectifs de la saison",
    casUsage: "Fixer un temps à battre ou un nombre d'épreuves pour la saison en cours et suivre votre progression.",
    etapes: [
      "Ouvrir « Mon espace » (compte rattaché à votre fiche), puis l'onglet « Objectifs ».",
      "Cliquer sur « Ajouter un objectif » et choisir « Un temps à battre » (discipline et temps cible au format H:MM:SS) ou « Nombre d'épreuves ».",
      "Cliquer sur « Enregistrer » : la progression se calcule sur vos résultats validés de la saison, et « Atteint » s'affiche une fois l'objectif tenu.",
      "Utiliser « Modifier » ou « Supprimer » sur la ligne d'un objectif : « Supprimer » demande d'abord une confirmation (« Supprimer cet objectif ? »). Vos objectifs sont privés, et ne se fixent que sur la saison en cours (les saisons passées sont en lecture seule).",
    ],
    captures: [],
  },
  {
    id: "recap-saison",
    titre: "Récap de saison",
    casUsage: "Relire votre saison close : épreuves, podiums, challenges et meilleurs temps.",
    etapes: [
      "Ouvrir « Mon espace » (compte rattaché à votre fiche), puis cliquer sur « Récap de la saison passée » dans la carte « Mes chiffres ».",
      "Lire les chiffres de la saison, vos meilleurs temps et la liste de vos épreuves.",
      "Passer d'une année à l'autre avec « Saison précédente » et « Saison suivante ». Seuls vos résultats validés y figurent.",
    ],
    captures: [],
  },
  {
    id: "carte-resultat",
    titre: "Carte résultat à partager",
    casUsage: "Télécharger une image de votre résultat (épreuve, temps, classements) à partager.",
    etapes: [
      "Depuis « Mon espace », cliquer sur « Ma carte résultat » sous votre dernier résultat.",
      "Ou ouvrir un de vos résultats depuis « Résultats », puis cliquer sur « Télécharger l'image » en haut de la page.",
      "L'image est créée sur votre appareil et téléchargée : elle ne montre que votre ligne, aucun autre athlète. Aucune validation n'est nécessaire. Le bouton n'apparaît pas sur un relais, ni sur un résultat encore en attente de validation.",
    ],
    captures: [],
  },
  {
    id: "reclamer-resultat",
    titre: "Réclamer un résultat",
    casUsage: "Faire déplacer sur votre fiche un résultat qui est le vôtre mais rangé sur une autre fiche, celle d'un homonyme par exemple.",
    etapes: [
      "Depuis « Résultats », ouvrir l'épreuve puis le résultat concerné (compte rattaché à votre fiche).",
      "Cliquer sur « Ce résultat est à moi » en haut de la page.",
      "Attendre le club : « Réclamation en attente » s'affiche, il vérifie qu'il s'agit bien de vous puis déplace le résultat sur votre fiche. Vous pouvez la retirer avec « Annuler la réclamation ».",
      "Sur un relais, le bouton se lit « Je faisais partie de cette équipe » : le club ajoute alors votre fiche à l'équipe.",
      "Un relais, un swimrun ou un raid publié sous le seul nom d'équipe : dans « Mon espace », carte « Un résultat d'équipe manque ? », chercher le nom de l'équipe puis cliquer sur « C'était mon équipe », qui envoie la même demande au club.",
      "En cas de refus, un message le rappelle sur ce résultat. Le bouton n'apparaît pas sur un résultat encore en attente de validation, ni sur un résultat déjà rangé sur votre fiche.",
    ],
    captures: [],
  },
  {
    id: "supprimer-compte",
    titre: "Supprimer votre compte",
    casUsage: "Effacer votre compte, vos connexions, rôles et groupes, sans retirer vos résultats ni votre fiche.",
    etapes: [
      "Ouvrir « Mon compte » depuis le menu de votre compte, dans la navigation.",
      "Descendre à la carte « Zone sensible » et cliquer sur « Supprimer mon compte ».",
      "Lire la confirmation « Supprimer votre compte ? » puis confirmer : la suppression est immédiate, sans validation du club.",
      "Vos objectifs de saison et vos réclamations de résultat en attente sont effacés avec le compte. Vos résultats et votre fiche athlète restent publiés. Vous pourrez vous reconnecter plus tard : un compte neuf, sans rôle, sera créé, et un nouveau rattachement demandera une nouvelle validation du club.",
    ],
    captures: [],
  },
];
