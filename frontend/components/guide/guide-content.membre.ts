import type { GuideSection } from "./types";

export const GUIDE_MEMBRE: GuideSection[] = [
  {
    id: "dashboard",
    titre: "Tableau de bord",
    casUsage: "Voir d'un coup d'œil la saison du club : résultats récents, classement et répartition par discipline.",
    etapes: [
      "Ouvrir « Tableau de bord » depuis la navigation principale.",
      "Choisir la ou les saisons à afficher avec le sélecteur de saison.",
      "Basculer entre classement scratch et par catégorie, ou filtrer par discipline, si besoin.",
    ],
    captures: [{ src: "/guide/membre/dashboard.jpg", alt: "Tableau de bord du club avec classement et épreuves récentes" }],
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
      "Filtrer par saison, portée (club ou toutes) ou recherche libre.",
      "Cliquer sur une épreuve pour en voir le classement complet.",
    ],
    captures: [{ src: "/guide/membre/resultats.jpg", alt: "Liste des résultats avec filtres" }],
  },
  {
    id: "comparaison",
    titre: "Comparaison",
    casUsage: "Comparer sa performance sur une épreuve à une édition précédente ou à un autre athlète.",
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
      "Vérifier le fournisseur détecté, puis lancer l'import.",
    ],
    captures: [{ src: "/guide/membre/ajouter.jpg", alt: "Formulaire d'ajout d'une épreuve par URL" }],
  },
  {
    id: "benevolat",
    titre: "Bénévolat",
    casUsage: "Créditer un athlète du club pour une activité de bénévolat, comptée dans son quota de saison.",
    etapes: [
      "Ouvrir « Bénévolat » depuis la navigation (section « Club »).",
      "Rechercher l'athlète concerné et décrire l'activité effectuée.",
      "Envoyer la déclaration : elle est instruite par un administrateur avant de compter pour le quota.",
    ],
    captures: [{ src: "/guide/membre/benevolat.jpg", alt: "Formulaire de déclaration de bénévolat" }],
  },
];
