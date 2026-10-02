import type { GuideSection } from "./types";

export const GUIDE_ADMIN: GuideSection[] = [
  {
    id: "epreuves",
    titre: "Épreuves",
    casUsage: "Corriger ou retirer une épreuve du catalogue. Ces actions sont irréversibles et tracées.",
    etapes: [
      "Ouvrir « Épreuves » depuis la navigation admin.",
      "Retrouver l'épreuve par recherche, puis ouvrir sa fiche de correction.",
      "Corriger les champs nécessaires, ou retirer l'épreuve si elle est en doublon.",
    ],
    captures: [{ src: "/guide/admin/epreuves.jpg", alt: "Écran de gestion des épreuves" }],
  },
  {
    id: "fournisseurs",
    titre: "Fournisseurs en attente",
    casUsage: "Fournisseurs de chronométrage non pris en charge, signalés automatiquement lors d'un import en échec.",
    etapes: [
      "Ouvrir « Fournisseurs en attente » depuis la navigation admin.",
      "Examiner un lien signalé pour évaluer si le fournisseur mérite un nouveau scraper.",
    ],
    captures: [{ src: "/guide/admin/fournisseurs.jpg", alt: "Liste des fournisseurs de chronométrage en attente" }],
  },
  {
    id: "doublons",
    titre: "Doublons suspects",
    casUsage:
      "Paires d'épreuves qui désignent probablement le même événement — même URL, même identifiant de plateforme, ou noms proches à la même date.",
    etapes: [
      "Ouvrir « Doublons suspects » depuis la navigation admin.",
      "Examiner une paire suspecte, puis fusionner ou écarter selon le cas.",
    ],
    captures: [{ src: "/guide/admin/doublons.jpg", alt: "Liste des paires d'épreuves suspectées doublons" }],
  },
  {
    id: "droits",
    titre: "Droits des rôles",
    casUsage:
      "Un rôle porte des pouvoirs ; les personnes portent des rôles. Une recomposition s'applique dès la requête suivante de chaque porteur, sans reconnexion.",
    etapes: [
      "Ouvrir « Droits des rôles » depuis la navigation admin (section « Gestion des utilisateurs »).",
      "Sélectionner un rôle, puis cocher ou décocher les pouvoirs qu'il porte.",
    ],
    captures: [{ src: "/guide/admin/droits.jpg", alt: "Composition des pouvoirs d'un rôle" }],
  },
  {
    id: "quality",
    titre: "Revalidation qualité",
    casUsage: "Les épreuves dont l'indice de fiabilité doute. Inspecter, corriger, puis trancher — chaque décision est tracée.",
    etapes: [
      "Ouvrir « Revalidation qualité » depuis la navigation admin.",
      "Inspecter une épreuve signalée, corriger si besoin, puis trancher : « Marquer fiable », « Marquer douteuse », ou « Revenir à l'avis calculé » pour annuler un verdict manuel.",
    ],
    captures: [{ src: "/guide/admin/quality.jpg", alt: "Liste des épreuves en revalidation qualité" }],
  },
  {
    id: "batches",
    titre: "Batches",
    casUsage:
      "Relancer la récupération des épreuves déjà enregistrées, importer une liste d'épreuves depuis un fichier, et relire le bilan des lancements précédents.",
    etapes: [
      "Ouvrir « Batches » depuis la navigation admin.",
      "Lancer un rescrape ou un import de liste, puis suivre sa progression.",
      "Consulter le bilan des lancements précédents en bas de l'écran.",
    ],
    captures: [{ src: "/guide/admin/batches.jpg", alt: "Écran de lancement des batches" }],
  },
  {
    id: "groupes",
    titre: "Groupes d'appartenance",
    casUsage:
      "À quoi chacun appartient — le Codir, les officiels, une section. Un groupe n'accorde aucun droit : ce que l'on peut faire vient des rôles.",
    etapes: [
      "Ouvrir « Groupes d'appartenance » depuis la navigation admin.",
      "Sélectionner un groupe, puis ajouter ou retirer un membre.",
    ],
    captures: [{ src: "/guide/admin/groupes.jpg", alt: "Composition d'un groupe d'appartenance" }],
  },
  {
    id: "utilisateurs",
    titre: "Rôles des utilisateurs",
    casUsage: "Qui s'est connecté au moins une fois, et ce que chacun porte. Un rôle prend effet à la requête suivante, sans reconnexion.",
    etapes: [
      "Ouvrir « Rôles des utilisateurs » depuis la navigation admin.",
      "Retrouver la personne concernée, puis lui attribuer ou retirer un rôle.",
    ],
    captures: [{ src: "/guide/admin/utilisateurs.jpg", alt: "Liste des utilisateurs et de leurs rôles" }],
  },
  {
    id: "journal",
    titre: "Journal d'administration",
    casUsage: "L'historique des gestes d'administration sur les données — qui, quoi, quand. Rien ici ne s'annule.",
    etapes: [
      "Ouvrir « Journal d'administration » depuis la navigation admin.",
      "Parcourir l'historique page par page pour retrouver un geste précis.",
    ],
    captures: [{ src: "/guide/admin/journal.jpg", alt: "Journal des gestes d'administration" }],
  },
  {
    id: "maintenance",
    titre: "Maintenance",
    casUsage:
      "Les gestes sans retour : vider les résultats, ou vider le catalogue entier. Rien ici ne se répare — chaque geste annonce son ampleur avant d'agir.",
    etapes: [
      "Ouvrir « Maintenance » depuis la navigation admin.",
      "Lire attentivement l'ampleur du geste annoncée, puis confirmer si voulu.",
    ],
    captures: [{ src: "/guide/admin/maintenance.jpg", alt: "Écran de maintenance et purges globales" }],
  },
  {
    id: "retours-utilisateurs",
    titre: "Retours utilisateurs",
    casUsage: "Signalements de bug et retours soumis depuis le bouton du site public.",
    etapes: [
      "Ouvrir « Retours utilisateurs » depuis la navigation admin.",
      "Ouvrir un signalement « Nouveau », puis changer son statut une fois instruit.",
    ],
    captures: [{ src: "/guide/admin/retours-utilisateurs.jpg", alt: "File des retours utilisateurs" }],
  },
  {
    id: "variantes-club",
    titre: "Variantes de club",
    casUsage:
      "Regrouper les orthographes d'un même club — hors TCN, qui garde son propre réglage — sous un nom affiché commun, pour « Top clubs » et le filtre du classement.",
    etapes: [
      "Ouvrir « Variantes de club » depuis la navigation admin.",
      "Ajouter une orthographe au groupe du club concerné, ou en créer un nouveau.",
    ],
    captures: [{ src: "/guide/admin/variantes-club.jpg", alt: "Regroupement des orthographes d'un club" }],
  },
  {
    id: "portee-compteurs",
    titre: "Portée des compteurs",
    casUsage:
      "Les orthographes sous lesquelles un chronométreur désigne le club, et les disciplines que les compteurs de triathlon laissent de côté.",
    etapes: [
      "Ouvrir « Portée des compteurs » depuis la navigation admin.",
      "Ajouter une orthographe de club, ou ajuster les disciplines couvertes.",
    ],
    captures: [{ src: "/guide/admin/portee-compteurs.jpg", alt: "Configuration de la portée des compteurs" }],
  },
  {
    id: "benevolat-validation",
    titre: "Bénévolat",
    casUsage:
      "Déclarations de crédit d'athlète en attente, soumises par un membre depuis la page publique de bénévolat : accepter ou refuser.",
    etapes: [
      "Ouvrir « Bénévolat » depuis la navigation admin.",
      "Examiner une déclaration en attente, puis l'accepter ou la refuser.",
    ],
    captures: [{ src: "/guide/admin/benevolat-validation.jpg", alt: "File des déclarations de bénévolat en attente" }],
  },
  {
    id: "validation-epreuves",
    titre: "Validation des épreuves",
    casUsage:
      "Les bénévoles vérifient un à un les résultats importés, sous le mot de passe bénévoles : corriger, réattribuer à la bonne fiche, valider ou signaler.",
    etapes: [
      "Ouvrir « Validation des épreuves » depuis la navigation, puis saisir le mot de passe bénévoles.",
      "Choisir un résultat dans la file : son détail s'ouvre.",
      "« Réattribuer à » : rechercher l'athlète par son nom et le choisir quand le résultat est crédité à la mauvaise fiche. Rien n'est enregistré tant que vous n'avez pas cliqué sur « Enregistrer » ou « Valider ce résultat ».",
      "« Valider ce résultat » enregistre les modifications en cours et passe au suivant.",
      "« Signaler non conforme », puis « Confirmer le signalement » : le résultat passe dans l'onglet « Non conformes », d'où « Lever le signalement » le fait revenir. Les modifications non enregistrées sont perdues.",
    ],
    captures: [
      {
        src: "/guide/admin/validation-epreuves.jpg",
        alt: "Résultat en cours de vérification : un autre athlète choisi dans « Réattribuer à », modification pas encore enregistrée",
      },
    ],
  },
  {
    id: "acces-backoffice",
    titre: "Accès et mots de passe",
    casUsage:
      "Un seul écran pour tout ce qui ouvre ou ferme un accès : adresses autorisées au back-office, code d'accès du site, mot de passe bénévoles, sessions ouvertes.",
    etapes: [
      "Ouvrir « Accès et mots de passe » depuis la navigation admin.",
      "Adresses autorisées : ajouter ou retirer une adresse. Une adresse retirée perd l'accès immédiatement.",
      "Code d'accès du site : le remplacer par une saisie ou en générer un. Il n'est plus lisible une fois enregistré, et le changer déconnecte les adhérents, qui devront saisir le nouveau.",
      "Mot de passe bénévoles : même geste, pour la page de vérification des résultats réservée aux bénévoles.",
      "Fermer les sessions : par adresse depuis la liste, ou toutes à la fois en bas de l'écran, vous compris.",
    ],
    captures: [{ src: "/guide/admin/acces-backoffice.jpg", alt: "Liste des adresses autorisées au back-office" }],
  },
  {
    id: "pages-publiques",
    titre: "Gestes sur les pages publiques",
    casUsage:
      "Certains gestes d'administration se font depuis la fiche d'un athlète, sans passer par le back-office : ils n'apparaissent qu'aux comptes qui en ont le pouvoir.",
    etapes: [
      "Ouvrir la fiche de l'athlète avec la loupe de la navigation (ou ⌘K, Ctrl K), ou depuis un classement.",
      "« Corriger la fiche » : modifier le nom, le prénom, la date de naissance ou le club actuel. Un club corrigé à la main n'est plus réécrit par les imports suivants.",
      "« Valider la saison » : choisir la saison, lire le décompte des épreuves et du bénévolat affiché dessous, puis valider. Une saison déjà validée propose « Dévalider la saison ».",
      "Dans la liste de ses épreuves, « Rattacher » déplace un résultat vers la bonne fiche, « Supprimer » le retire, et « Attribuer aux équipiers » répartit un résultat de relais.",
    ],
    captures: [
      {
        src: "/guide/admin/pages-publiques.jpg",
        alt: "Fiche athlète vue par un administrateur, avec les boutons « Corriger la fiche » et « Valider la saison »",
      },
      {
        src: "/guide/admin/pages-publiques-epreuves.jpg",
        alt: "Liste des épreuves d'un athlète vue par un administrateur, avec les boutons « Supprimer » et « Rattacher » sur chaque ligne",
      },
    ],
  },
];
