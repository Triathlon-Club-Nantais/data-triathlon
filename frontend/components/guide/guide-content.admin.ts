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
      "Revenir sur une mise à l'écart : déplier « Paires écartées » sous la liste, puis « Annuler » sur la paire. Elle revient dans les doublons suspects.",
    ],
    captures: [{ src: "/guide/admin/doublons.jpg", alt: "Liste des paires d'épreuves suspectées doublons" }],
  },
  {
    id: "identites",
    titre: "Identités des athlètes",
    casUsage:
      "Fiches qui mêlent deux personnes, ou paires de fiches qui désignent probablement la même. Chaque carte nomme son motif, rappelle le geste à choisir et offre ce geste sur place. Fusionner, rattacher et supprimer sont définitifs ; écarter une paire ou un cas et confirmer un club se reprennent.",
    etapes: [
      "Ouvrir « Identités des athlètes » depuis la navigation admin. Le nom d'une fiche ouvre sa page publique.",
      "Deux dossards sur une même épreuve : deux personnes partagent la fiche. Sur la ligne du résultat en conflit, « Séparer » le déplace vers une nouvelle fiche, « Rattacher » vers la fiche existante de l'autre personne, et « Supprimer » retire un doublon, sans retour. Deux dossards légitimes (un relais et une épreuve individuelle) : « Écarter » sort le cas de la liste sans toucher aux résultats, jusqu'à ce qu'une autre épreuve entre en conflit.",
      "Un autre club sur une fiche de membre : si la personne a changé de club, « Confirmer ce club ». Aucun résultat ne bouge, et le club n'est plus signalé pour cette fiche. Si c'est un homonyme, « Séparer des résultats » coche ses résultats et les déplace vers une nouvelle fiche.",
      "Homonyme du club : même personne, « Fusionner », en choisissant la fiche conservée (l'autre est supprimée, ses résultats, validations de saison, bénévolat et compte membre passent sur la fiche conservée). Deux personnes : « Écarter ». La paire sort de la liste, aucune donnée n'est modifiée.",
      "Nom et prénom inversés, ou nom complet face à une fiche découpée : « Corriger la fiche » fautive pour remettre nom et prénom en place, ou « Fusionner ». Une même épreuve courue par les deux fiches prouve deux personnes : « Écarter ».",
      "Fiche recréée sur une graphie déjà fusionnée : même personne, « Fusionner ». Variante posée par erreur : « Voir les variantes » ouvre la fiche qui la porte, où « Retirer » la détache.",
      "Revenir sur un arbitrage : sous la liste, déplier « Paires écartées », « Cas écartés » ou « Clubs confirmés », puis « Annuler ». La paire ou le cas revient dans la revue, ou le club est de nouveau signalé pour la fiche. Si les deux fiches d'une paire portent la même clé, la prochaine reprise peut les fusionner, sans retour.",
    ],
    captures: [],
  },
  {
    id: "droits",
    titre: "Droits des rôles",
    casUsage:
      "Un rôle porte des pouvoirs ; les personnes portent des rôles. Une recomposition s'applique dès la requête suivante de chaque porteur, sans reconnexion.",
    etapes: [
      "Ouvrir « Droits des rôles » depuis la navigation admin (section « Gestion des utilisateurs »).",
      "Sélectionner un rôle, puis cocher ou décocher les pouvoirs qu'il porte.",
      "Rôles fournis, à ajuster librement : « Bureau » (accès, adhérents, licenciés, rattachements, groupes, oppositions, retours), « Bénévole data » (épreuves, fiches, homonymes, chronométreurs signalés, rattachements), « Validation » (saisons et bénévolat), « Encadrant jeunes ». Ils se cumulent. Les suppressions, purges, lancements de batch et l'attribution des rôles restent à l'administrateur.",
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
      "La file ne montre que les épreuves encore sans avis, celles que compte la pastille de la navigation : un avis posé, fiable ou douteux, l'en sort. « Voir aussi les épreuves déjà jugées » y ajoute celles marquées douteuses, pour revenir sur un verdict.",
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
    id: "membres",
    titre: "Licenciés du club",
    casUsage:
      "La liste des licenciés publiée par la FFTri, saison par saison. Un licencié rattaché à sa fiche fait compter ses résultats de la saison pour le club, même sans libellé de club. Chaque changement recalcule les compteurs du club.",
    etapes: [
      "Ouvrir « Licenciés du club » depuis la navigation admin, puis choisir la saison.",
      "« Relire la liste FFTri » remplace la liste de la saison en cours par celle de la FFTri. Chaque licencié est rattaché à la fiche de même nom quand elle est unique ; les rattachements faits à la main sont conservés, et une personne inscrite aux oppositions n'y entre pas.",
      "« Licenciés à rattacher » liste ceux sans fiche à leur nom ou avec plusieurs fiches à ce nom. « Rattacher à une fiche » : rechercher l'athlète, puis le choisir.",
      "Revenir sur un rattachement : déplier « Rattachements faits à la main », puis « Annuler ». Le licencié reprend son rattachement automatique, ou revient dans les licenciés à rattacher.",
      "Saison passée : choisir l'année de début et un fichier .csv ou .xlsx avec une colonne « Nom » et une colonne « Prénom », puis « Importer ». Le fichier remplace toute la liste de cette saison.",
    ],
    captures: [],
  },
  {
    id: "adresses-adherents",
    titre: "Adresses d'adhérents",
    casUsage:
      "Les adresses e-mail des adhérents, saison par saison. Elles reconnaissent un adhérent à la connexion. Distinctes des adresses autorisées au back-office : y figurer ne donne aucun pouvoir d'administration.",
    etapes: [
      "Ouvrir « Adresses d'adhérents » depuis la navigation admin, puis choisir la saison.",
      "Exporter les contacts depuis AssoConnect (.xlsx ou .csv), choisir le fichier puis « Importer ». Seule la colonne « Email » (ou « E-mail », « Courriel ») est lue. L'import remplace les adresses importées de la saison : une adresse absente du fichier est retirée, les adresses ajoutées à la main restent. Le compte rendu donne les adresses ajoutées, retirées, inchangées et les lignes ignorées.",
      "Un adhérent dont l'adresse de connexion diffère de celle d'AssoConnect : saisir son adresse dans « Adresse à ajouter », puis « Ajouter ». Elle survit aux imports suivants.",
      "« Retirer » ôte une adresse, après confirmation, quelle que soit son origine.",
      "La saison qui compte est la saison en cours dès qu'elle a une adresse importée ; avant le premier import de septembre, celle de la saison précédente continue de compter, et les adresses ajoutées à la main pour la saison en cours comptent aussi. Les saisons plus anciennes sont supprimées par la purge hebdomadaire.",
    ],
    captures: [],
  },
  {
    id: "rattachements",
    titre: "Rattachements de fiche",
    casUsage:
      "Les demandes d'utilisateurs connectés qui se reconnaissent sur une fiche athlète (« C'est moi »). Aucune n'est validée d'office, même quand l'adresse du compte figure sur la liste d'adhérents : la liste ne porte que des adresses, pas de nom. Un compte rattaché retrouve sa fiche dans Mon espace, et il est reconnu adhérent tant que sa fiche est licenciée au club pour la saison.",
    etapes: [
      "Ouvrir « Rattachements de fiche » depuis la navigation admin. La pastille compte les demandes en attente.",
      "Pour chaque demande, comparer le compte (nom affiché, adresse) à la fiche demandée, avec les indices : licencié TCN de la saison rattaché à la fiche, adresse présente sur la liste d'adhérents, comptes déjà rattachés à la fiche (une même personne peut avoir plusieurs comptes).",
      "« Valider » rattache la fiche au compte ; « Refuser » laisse le compte sans fiche, l'utilisateur voit la demande refusée dans son menu. Les deux gestes sont inscrits au journal d'administration.",
      "L'utilisateur peut se détacher lui-même depuis son menu ; une nouvelle demande repasse alors par cette file.",
      "« Comptes rattachés », sous la file, liste les comptes et dit si leur fiche est licenciée cette saison (ceux dont la licence ne court plus en tête). « Détacher », après confirmation, retire la fiche d'un compte, par exemple au départ d'un adhérent ; le geste est journalisé.",
    ],
    captures: [],
  },
  {
    id: "oppositions",
    titre: "Oppositions",
    casUsage:
      "Les personnes qui ont demandé le retrait de leurs résultats. Une opposition anonymise leurs résultats, et tout résultat importé ensuite à ce nom arrive anonyme. Ce geste est définitif. Aucun nom n'est affiché : la base n'en garde pas.",
    etapes: [
      "Ouvrir « Oppositions » depuis la navigation admin.",
      "Personne sans fiche, ou demande reçue par courrier : saisir le nom, le prénom et la date de la demande, puis « Enregistrer l'opposition ». Le décompte des résultats concernés s'affiche, homonymes compris, avant « Anonymiser définitivement ».",
      "Personne qui a une fiche : le geste se fait aussi depuis sa page publique, par « Appliquer une opposition ».",
      "Le tableau des oppositions appliquées donne pour chacune la date de la demande, celle de l'application, le délai et qui l'a appliquée. « Hors délai légal » signale une opposition appliquée plus de 30 jours après la demande.",
    ],
    captures: [],
  },
  {
    id: "benevolat-validation",
    titre: "Crédits bénévoles",
    casUsage:
      "Déclarations de crédit d'athlète en attente, soumises par un membre depuis la page publique de bénévolat : accepter ou refuser. L'écran vit dans l'espace Encadrement.",
    etapes: [
      "Ouvrir « Crédits bénévoles » depuis l'espace Encadrement.",
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
    id: "jeunes",
    titre: "Jeunes",
    casUsage:
      "Dans l'espace Encadrement, le suivi des jeunes triathlètes : leurs profils, leurs groupes, le calendrier des entraînements et l'appel de présence. Données personnelles de mineurs : la lecture suffit pour consulter, les gestes d'écriture demandent un pouvoir de plus.",
    etapes: [
      "« Profils » : saisir prénom, nom et date de naissance, puis « Créer le profil ». Ouvrir un profil, puis « Modifier le profil » pour le contact d'urgence, les notes et la fin d'adhésion. « Ajouter au journal » consigne une entrée datée. Le numéro du contact d'urgence s'y appelle d'un toucher.",
      "Fin d'adhésion : à renseigner quand le jeune quitte le club. Le profil, son journal et ses présences sont alors supprimés définitivement à la fin de la saison suivante, par la purge hebdomadaire.",
      "Chaque profil affiche sa catégorie FFTri de la saison en cours (« Catégorie inconnue » sans date de naissance), et la liste se filtre par catégorie, pratique pour constituer un groupe.",
      "« Groupes d'entraînement » : saisir un nom, puis « Créer le groupe ». Ouvrir un groupe pour le renommer, « Ajouter un jeune » ou « Retirer » un membre ; « Supprimer le groupe » demande confirmation. La fiche d'un profil liste aussi ses groupes, avec « Ajouter à un groupe » et « Retirer ». Un jeune dont l'adhésion est terminée y reste signalé, mais n'est plus inscrit d'office.",
      "Inscription d'office : cocher des « Groupes visés » à la création ou à la modification d'une séance inscrit leurs membres. Les séances à venir dont l'appel n'a pas commencé suivent ensuite les changements de composition des groupes ; une séance passée ou déjà pointée ne bouge plus, et un jeune inscrit à la main n'est jamais désinscrit par un groupe.",
      "« Nouvelle récurrence », au calendrier : choisir le jour, l'heure, la période, le lieu et les groupes. L'écran annonce le nombre de séances avant « Créer les séances » (53 au plus). Modifier la récurrence change ses séances à venir non pointées, sauf celles modifiées une par une ; la supprimer retire ces séances après confirmation, les autres restent au calendrier.",
      "« Calendrier des entraînements » : renseigner date, heure, lieu et type, puis « Créer la séance ». Les séances à venir viennent en tête, celle du jour marquée « Aujourd'hui », les passées en dessous. Une séance ouverte se modifie, inscrit un jeune depuis la liste, et « Désinscrire » retire une inscription, qui se refait aussi simplement. « Ouvrir l'appel » mène à son appel ; « Supprimer la séance » l'efface avec ses inscriptions et ses présences, après confirmation.",
      "« Appel » ouvre la séance du jour, la crée par « Créer la séance du jour » (avec les groupes cochés) s'il n'y en a pas, ou demande laquelle choisir s'il y en a plusieurs.",
      "« Appel de début » : le compteur en tête dit combien de présents, d'absents et de jeunes à pointer. « Présent » ou « Absent » pour chaque jeune inscrit (le pointage se change d'un clic), « Ajouter un jeune » l'inscrit et le pointe présent, « Ajouter une note » écrit dans son journal, « Enregistrer la note » garde la note de séance.",
      "« Appel de fin » : cocher chaque jeune présent au début une fois retrouvé, jusqu'à ce qu'aucun ne manque. Rien n'y est enregistré : quitter l'onglet remet l'appel de fin à zéro.",
    ],
    captures: [],
  },
  {
    id: "pages-publiques",
    titre: "Gestes sur les pages publiques",
    casUsage:
      "Certains gestes d'administration se font depuis la fiche d'un athlète ou d'une épreuve, sans passer par le back-office : ils n'apparaissent qu'aux comptes qui en ont le pouvoir.",
    etapes: [
      "Ouvrir la fiche de l'athlète avec la loupe de la navigation (ou ⌘K, Ctrl K), ou depuis un classement.",
      "« Corriger la fiche » : modifier le nom, le prénom, la date de naissance ou le club actuel. Un club corrigé à la main n'est plus réécrit par les imports suivants.",
      "« Valider la saison » : choisir la saison, lire le décompte des épreuves et du bénévolat affiché dessous, puis valider. Une saison déjà validée propose « Dévalider la saison ».",
      "Dans la liste de ses épreuves, « Rattacher » déplace un résultat vers la bonne fiche, « Supprimer » le retire, et « Attribuer aux équipiers » répartit un résultat de relais.",
      "« Fusionner avec une autre fiche » : rechercher l'autre fiche de la même personne, puis choisir celle à conserver. L'autre est supprimée sans retour : ses résultats, ses validations de saison, son bénévolat et son compte membre passent sur la fiche conservée. Sa graphie y reste en général rattachée comme variante : quand elle diffère de celle de la fiche conservée et n'est pas celle d'un homonyme distingué.",
      "« Séparer des résultats », au-dessus de la liste des épreuves : cocher les résultats d'une autre personne du même nom, puis « Séparer vers une nouvelle fiche ». Les deux fiches sont jugées distinctes et ne seront plus proposées à la fusion.",
      "« Variantes d'identité » liste les graphies qu'une fusion a rattachées à la fiche : l'import y range les résultats publiés sous elles. « Retirer » détache une variante posée par erreur ; les résultats déjà rattachés restent en place.",
      "Sur la page d'une épreuve : « Corriger l'épreuve » modifie ses informations, « Avis de fiabilité » la marque fiable ou douteuse, ou revient à l'avis calculé.",
      "« Fusionner avec une autre épreuve » : chercher l'autre épreuve par son nom ou son numéro, sans contrainte de date, puis choisir celle à conserver après l'aperçu. L'autre est supprimée : ses résultats sans correspondance disparaissent, et son adresse devient une source de l'épreuve conservée. « Supprimer l'épreuve » la retire. Ces deux gestes sont irréversibles et tracés dans le journal.",
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
