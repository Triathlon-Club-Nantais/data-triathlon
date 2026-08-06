# Feature Specification: Lancer les batches de production depuis l'interface d'administration

**Feature Branch**: `20260806-143754-ops-batch-runs`

**Created**: 2026-08-06

**Status**: Draft

**Input**: issue [#47](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/47) — « lancer les batches en production, déclenchés depuis /admin »

## Contexte

Les batches de mise à jour des résultats (`import-sheet`, `rescrape-db`) ne se
lancent aujourd'hui que depuis un poste de développement pointé sur la base de
production. Rien n'en garde trace, rien n'alerte en cas d'échec, et le club
dépend d'une seule personne pour les exécuter.

Cette fonctionnalité déplace le geste dans l'interface d'administration, désormais
protégée par l'authentification (#114) et les pouvoirs (#115).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Relancer la récupération des résultats déjà connus (Priority: P1)

Un administrateur constate que les résultats d'un chronométreur ont changé à la
source (correction d'un classement, ajout de participants). Depuis l'écran
d'administration, il choisit quelles épreuves reprendre — celles d'un
chronométreur donné, celles qui n'ont pas été rafraîchies depuis N jours, ou un
nombre borné d'entre elles — et lance la reprise. L'écran lui montre que le
traitement est en cours, puis son bilan : combien d'épreuves traitées, combien de
participants ajoutés ou mis à jour, et lesquelles ont échoué et pourquoi.

**Why this priority**: C'est le besoin qui a ouvert l'issue, et la tranche la plus
petite qui supprime à elle seule la dépendance au poste de développement. Elle
livre aussi tout le socle d'exécution dont les autres histoires se servent.

**Independent Test**: Lancer une reprise bornée à 5 épreuves en mode simulation
depuis l'écran, et retrouver son bilan sans ouvrir un terminal.

**Acceptance Scenarios**:

1. **Given** un administrateur porteur du pouvoir de lancement, **When** il lance
   une reprise limitée à 5 épreuves, **Then** l'écran indique un traitement en
   cours puis affiche son bilan chiffré.
2. **Given** une reprise déjà en cours, **When** un second lancement est demandé,
   **Then** il est refusé avec un message qui nomme la raison, et aucun second
   traitement ne démarre.
3. **Given** un utilisateur connecté sans le pouvoir de lancement, **When** il
   tente de lancer une reprise, **Then** la demande est refusée et aucun
   traitement ne démarre.
4. **Given** une reprise dont **toutes** les épreuves ont échoué, **When** elle
   se termine, **Then** elle est signalée comme en échec sans qu'un humain ait à
   lire le détail du bilan.
5. **Given** une reprise dont une partie seulement des épreuves a échoué,
   **When** elle se termine, **Then** elle est signalée comme réussie, et les
   épreuves fautives sont listées avec leur cause.

---

### User Story 2 - Importer une liste d'épreuves depuis un fichier (Priority: P2)

Un administrateur dispose d'un fichier (tableur exporté en `.csv` ou `.xlsx`)
listant des épreuves auxquelles des adhérents ont participé, avec quelque part
une colonne de liens vers les résultats. Il téléverse ce fichier ; l'application
lui présente les colonnes qu'elle y a trouvées, en indiquant pour chacune combien
de liens elle contient, et met en avant la plus probable. Il confirme la colonne,
voit combien d'épreuves distinctes en seront tirées et combien de liens ne sont
pas exploitables, puis lance l'import. Le bilan est celui de l'histoire 1.

**Why this priority**: Remplace l'import depuis un Google Sheet figé dans le code
par une source que l'administrateur choisit lui-même, sans intervention technique.
Dépend du socle d'exécution livré par l'histoire 1.

**Independent Test**: Téléverser un `.csv` puis un `.xlsx` de quelques lignes,
désigner la colonne de liens, et vérifier que les épreuves correspondantes sont
importées.

**Acceptance Scenarios**:

1. **Given** un fichier `.csv` ou `.xlsx` valide, **When** l'administrateur le
   téléverse, **Then** l'application liste ses colonnes avec le nombre de liens
   détectés dans chacune et présélectionne celle qui en contient le plus.
2. **Given** une colonne désignée, **When** l'administrateur lance l'import,
   **Then** toutes les URL de cette colonne sont traitées, chaque épreuve n'étant
   traitée qu'une fois même si son lien figure sur plusieurs lignes.
3. **Given** une colonne contenant des liens vers des chronométreurs non
   supportés, **When** l'import est lancé, **Then** ces liens sont listés à part
   et ne comptent ni comme succès ni comme échec.
4. **Given** un fichier dont l'extension, la taille ou le nombre de liens dépasse
   les bornes admises, **When** il est téléversé, **Then** il est refusé avec un
   message qui dit laquelle des trois bornes est franchie — jamais tronqué en
   silence.
5. **Given** un fichier téléversé, **When** l'administrateur abandonne sans
   lancer d'import, **Then** aucune trace du fichier ne subsiste côté serveur.

---

### User Story 3 - Rafraîchir les résultats sans intervention (Priority: P3)

Les résultats les plus anciennement rafraîchis sont repris automatiquement à
intervalle régulier, sans que personne ne le demande. Un cycle dont toutes les
épreuves échouent est signalé, faute de quoi une panne de source pourrait durer
des semaines sans être vue.

**Why this priority**: Confort et fiabilité dans la durée ; sans valeur tant que
les histoires 1 et 2 n'ont pas prouvé qu'un traitement automatisé aboutit.

**Independent Test**: Attendre (ou déclencher) une occurrence planifiée et
retrouver son bilan au même endroit que ceux lancés à la main.

**Acceptance Scenarios**:

1. **Given** la planification active, **When** l'échéance survient, **Then** une
   reprise démarre sans intervention et son bilan est consultable comme les
   autres.
2. **Given** une reprise planifiée qui échoue en totalité, **When** elle se
   termine, **Then** l'échec est notifié sans consultation manuelle.

---

### Edge Cases

- **Fichier sans en-tête, ou dont la première ligne est vide** : l'application
  doit tout de même proposer des colonnes désignables plutôt que de refuser le
  fichier.
- **Colonne désignée ne contenant aucun lien** : refus explicite avant tout
  lancement, plutôt qu'un traitement vide compté comme réussi.
- **Cellules contenant du texte autour du lien**, un lien relatif, ou une valeur
  qui n'est pas une adresse : ignorées et comptées, jamais devinées.
- **Doublons dans la colonne** : une même épreuve n'est traitée qu'une fois, et
  le bilan dit combien de lignes ont été ramenées à combien d'épreuves.
- **Perte de la page pendant un traitement** : le traitement se poursuit, et son
  bilan reste consultable au retour — l'écran n'est pas ce qui exécute.
- **Traitement qui n'aboutit jamais** (source qui ne répond plus) : il ne bloque
  pas indéfiniment les lancements suivants.
- **Utilisateur porteur du pouvoir de consultation mais pas de lancement** : il
  voit les bilans, l'action de lancement lui est refusée.
- **Le cas symétrique — lancement sans consultation** : il lance, mais ne voit ni
  l'état courant ni les bilans. L'écran ne doit alors afficher **aucun bloc en
  erreur** à la place de la liste, et un lancement refusé lui dit qu'un
  traitement est en cours sans le nommer. C'est une combinaison légitime mais peu
  utile : les deux pouvoirs sont faits pour aller ensemble.
- **Interface indisponible** : un administrateur technique doit conserver un
  moyen documenté de lancer un batch sans elle.

## Requirements *(mandatory)*

### Functional Requirements

**Lancement**

- **FR-001**: Un administrateur MUST pouvoir lancer une reprise des résultats
  depuis l'interface d'administration, sans accès à un poste de développement.
- **FR-002**: Le lancement MUST proposer les mêmes critères de sélection que la
  commande existante : chronométreur, ancienneté du dernier rafraîchissement,
  nombre maximum d'épreuves, et mode simulation.
- **FR-003**: Le système MUST n'accepter qu'un **catalogue fermé** de traitements
  et d'options typées ; aucune commande ni option libre saisie par l'utilisateur
  ne MUST atteindre l'exécution.
- **FR-004**: Le système MUST refuser un lancement tant qu'un traitement est en
  cours, avec un message qui le dit, plutôt que d'en démarrer un second sur la
  même base.
- **FR-005**: Le lancement MUST exiger le pouvoir `batch:run` et la consultation
  des bilans le pouvoir `batch:read`, tous deux attribuables par rôle sans
  livraison de code.

**Import d'un fichier**

- **FR-006**: Un administrateur MUST pouvoir téléverser un fichier `.csv` ou
  `.xlsx` et se voir présenter la liste de ses colonnes.
- **FR-007**: Le système MUST indiquer, pour chaque colonne, le nombre de valeurs
  qui sont des liens, et présélectionner celle qui en porte le plus.
- **FR-008**: L'administrateur MUST désigner la colonne portant les liens de
  résultats ; le système ne MUST jamais la retenir sans confirmation.
- **FR-009**: Le système MUST traiter toutes les URL de la colonne désignée avec
  le même comportement que l'import existant : dédoublonnage des épreuves,
  mise à l'écart des chronométreurs non supportés, bilan par épreuve.
- **FR-010**: Avant lancement, le système MUST annoncer combien d'épreuves
  distinctes seront traitées et combien de liens sont écartés, et sur quel motif.
- **FR-011**: Le fichier téléversé ne MUST **jamais** être conservé côté serveur
  au-delà de la requête qui le traite.
- **FR-012**: Le système MUST refuser, avec un motif nommé, un fichier dont
  l'extension n'est pas admise, dont la taille dépasse la borne, ou dont la
  colonne désignée porte plus d'URL que la borne par lot. Un dépassement ne MUST
  jamais donner lieu à une troncature silencieuse.

**Exécution, suivi et bilan**

- **FR-013**: L'exécution d'un batch ne MUST pas dégrader la disponibilité du
  site public : elle ne se fait pas dans le processus qui sert les visiteurs.
- **FR-014**: L'administrateur MUST pouvoir voir l'état du traitement en cours et
  celui des derniers traitements terminés.
- **FR-015**: Le bilan MUST être consultable depuis l'interface, et comporter :
  épreuves ciblées, traitées et en erreur, participants ajoutés, mis à jour et
  déjà en base, et le détail (lien + cause) de chaque épreuve en erreur.
- **FR-016**: Un traitement dont **toutes** les épreuves ont échoué MUST être
  signalé comme en échec, sans lecture du détail ; un échec partiel MUST rester
  un succès.
- **FR-017**: Le système MUST conserver les contrats de sortie de la CLI
  existante — codes de sortie et séparation stdout/stderr — sur lesquels repose
  ce signalement (Principe IV).

**Planification**

- **FR-018**: Une reprise périodique MUST pouvoir s'exécuter sans intervention, et
  son bilan MUST être consultable au même endroit que ceux lancés à la main.
- **FR-019**: L'échec total d'une exécution planifiée MUST être notifié sans
  consultation manuelle.

**Repli**

- **FR-020**: Le lancement d'un batch MUST rester possible sans l'interface, par
  une voie documentée, pour le cas où celle-ci est indisponible.

### Key Entities

- **Lancement de batch** : une demande d'exécution — son auteur, son type
  (reprise filtrée ou import de fichier), ses options retenues, son horodatage,
  son état (en attente, en cours, terminé) et son issue (succès, succès partiel,
  échec total).
- **Bilan** : le résultat chiffré d'un lancement — compteurs en épreuves et en
  participants, et la liste des épreuves en erreur avec leur cause.
- **Colonne de fichier** : un en-tête présenté à l'administrateur, avec le nombre
  de liens qu'il contient et un aperçu de ses premières valeurs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur non-développeur lance une reprise et retrouve son
  bilan **sans ouvrir de terminal ni consulter le dépôt**.
- **SC-002**: Le geste complet « téléverser un fichier → désigner la colonne →
  lancer » se fait en **moins de 2 minutes** et en **3 actions** au plus.
- **SC-003**: **100 %** des lancements terminés dont toutes les épreuves ont
  échoué sont signalés comme tels ; **0 %** des échecs partiels le sont.
- **SC-004**: Pendant un batch, les pages publiques restent servies dans les
  mêmes temps qu'en dehors — aucune dégradation mesurable.
- **SC-005**: **Aucune écriture de fichier applicative** dans le chemin de
  traitement d'un téléversement — vérifiable par test, là où « rien ne subsiste
  sur le serveur » ne l'est pas depuis une plateforme sans accès shell.
- **SC-006**: **100 %** des tentatives de lancement sans le pouvoir requis sont
  refusées.
- **SC-007**: Une reprise périodique s'exécute sur au moins **4 échéances
  consécutives** sans intervention humaine. *Vérifiable seulement après mise en
  service — c'est un point de suivi (≈ J+30 après activation de la
  planification), pas un critère de fusion.*

## Assumptions

- **Le pouvoir suffit à autoriser** : l'inventaire de pouvoirs (#115) est en
  place, `batch:run` et `batch:read` s'y ajoutent sans changement de schéma.
- **Un seul batch à la fois** est la règle, et le second lancement est **refusé**
  plutôt que mis en file d'attente : une file d'attente ajouterait un état à
  suivre pour un besoin qui ne s'est jamais présenté.
- **L'historique consultable se limite aux 20 derniers lancements, 50 au plus**,
  et n'est pas dupliqué dans notre base : la plateforme d'exécution le conserve
  déjà.
- **Bornes retenues** : 2 Mo par fichier, 500 URL par lot. Elles viennent de la
  taille des fichiers réellement manipulés par le club, majorée ; le motif de
  refus les nomme.
- **Cadence de la reprise périodique** : hebdomadaire, de nuit, à confirmer
  après la première mesure de durée réelle d'une reprise complète.
- **Le Google Sheet cesse d'être une source côté interface**, remplacé par le
  téléversement. La commande CLI correspondante reste disponible tant que le
  Sheet sert d'amorçage.
- **La notification d'échec** emprunte celle de la plateforme d'exécution ; aucun
  canal d'alerte nouveau n'est introduit. **Le destinataire réel reste à
  constater** : pour une exécution planifiée, la plateforme notifie par défaut
  l'auteur de la dernière modification de la planification, ce qui n'est pas
  nécessairement la personne qui doit agir. Si le destinataire n'est pas le bon,
  cette hypothèse tombe et FR-019 rouvre le sujet d'un canal dédié.
- **Le fichier reste dans le navigateur** entre l'appel qui liste les colonnes et
  celui qui lance le batch : c'est ce qui permet FR-011 sans stockage temporaire.

## Dépendances

- Socle d'authentification (#114) et pouvoirs (#115) : livrés.
- Ciblage d'épreuves par URL dans la CLI (#46) : livré — c'est lui qui permet à
  l'import de fichier et à la reprise filtrée de partager un seul chemin
  d'exécution.
- Une plateforme d'exécution hors du service web, avec journal et notification
  d'échec : décision arrêtée dans #47.

## Hors périmètre

- Reprendre une épreuve à l'unité depuis l'interface : déjà couvert par l'import
  d'une URL sur le site public.
- Suivre la progression épreuve par épreuve en direct pendant un batch : le
  bilan à la fin suffit au besoin exprimé.
- Rejouer automatiquement les épreuves en erreur d'un batch précédent : la liste
  des échecs est fournie, le rejeu reste un geste demandé.
- Notifier par courriel ou messagerie du club : la notification de la plateforme
  d'exécution est retenue telle quelle.
