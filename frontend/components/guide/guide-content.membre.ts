import type { GuideSection } from "./types";

export const GUIDE_MEMBRE: GuideSection[] = [
  {
    id: "dashboard",
    titre: "Accueil et Mon espace",
    casUsage: "Prendre le pouls du club sur l'accueil, puis retrouver sa propre saison dans « Mon espace ».",
    etapes: [
      "Ouvrir « Accueil » depuis la navigation principale : le dernier direct du club et les tuiles mènent aux espaces.",
      "Ouvrir « Mon espace » pour votre saison et les dernières épreuves du club, puis choisir la ou les saisons à afficher avec le sélecteur de saison.",
      "Basculer entre classement scratch et par catégorie, ou filtrer par discipline, si besoin.",
    ],
    captures: [{ src: "/guide/membre/dashboard.jpg", alt: "Mon espace du club avec classement et épreuves récentes" }],
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
      "Cliquer sur « Choisir cet athlète » : un raccourci « Mes résultats » apparaît dans la navigation et dans les filtres de « Résultats », et sa saison s'affiche en tête de « Mon espace ».",
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
];
