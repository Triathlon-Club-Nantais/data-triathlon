# Feature Specification: Re-scrape à la demande d'une course depuis le back-office

**Feature Branch**: `20260813-183235-admin-rescrape-course`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "Re-scrape à la demande d'une course depuis le back-office (issue #118). Depuis le back-office, un administrateur peut déclencher un re-scrape d'une course déjà en base sans passer par la CLI — utile pour rafraîchir les résultats après correction côté chronométreur, ou rejouer un import qui avait échoué. Endpoint POST /api/v1/admin/courses/{id}/rescrape réutilisant rescrape_service existant (force=True, le cache TTL est court-circuité). Streaming SSE pour la progression, sur le même mécanisme que la bascule de source (#285) — pas un second mécanisme. UI : bouton « Re-scraper » sur la page course admin, avec barre de progression consommant le SSE. Métadonnées de la course mises à jour si changées chez le chronométreur, participations upsert par bib_number, orphelins d'identité nettoyés en fin de rescrape (comme rescrape-db CLI). Dépendances #115 (RBAC) et #116 (UI connexion) déjà closes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rafraîchir une course après correction chronométreur (Priority: P1)

Un administrateur du club constate que le chronométreur a corrigé des temps ou
des classements après publication. Depuis la page de la course, il déclenche
un nouveau scrape sans passer par la CLI, et voit la progression se dérouler
en direct jusqu'à confirmation que les résultats sont à jour.

**Why this priority**: C'est le scénario qui justifie la feature — jusqu'ici,
seule la CLI (`rescrape-db`) permet de rafraîchir une course, ce qui exclut un
administrateur non technique et impose un aller-retour vers quelqu'un qui a
accès au serveur.

**Independent Test**: Peut être testé seul en déclenchant un re-scrape sur une
course existante dont les temps source ont changé, et en vérifiant que le
classement affiché reflète la nouvelle donnée en fin d'opération.

**Acceptance Scenarios**:

1. **Given** un administrateur sur la page d'une course déjà importée,
   **When** il clique sur « Re-scraper »,
   **Then** une progression en temps réel s'affiche jusqu'à la fin de
   l'opération, sans qu'il ait à recharger la page.
2. **Given** un re-scrape en cours dont la progression est affichée,
   **When** l'opération se termine avec succès,
   **Then** les temps, classements et métadonnées de la course affichés sont
   ceux renvoyés par le chronométreur au moment du re-scrape.
3. **Given** une course dont l'identité (nom, date, type) publiée par le
   chronométreur ne correspond plus à celle enregistrée,
   **When** l'administrateur déclenche un re-scrape,
   **Then** il est refusé explicitement (cf. Edge Cases, FR-009) et la fiche
   course n'est pas modifiée — converger deux identités pour une même épreuve
   réelle est un geste distinct, hors périmètre (voir Amendement ci-dessous).

**Amendement (revue de code, post-implémentation)** : la version initiale de
ce scénario promettait une mise à jour du nom/date/type sur divergence. C'est
irréalisable sans affaiblir la garde de sécurité de FR-009, qui refuse déjà
toute divergence d'identité — les deux comportements sont mutuellement
exclusifs pour la même détection. `_require_same_event` (réutilisée de la
bascule de source, #285, research.md R3) est un refus **par construction**, et
`course_repository.get_or_create` ne réécrit jamais l'identité d'une course
déjà connue. Corriger un libellé erroné (nom, date, type) reste le geste déjà
existant `PATCH /admin/courses/{id}` (`courses:write`, #117,
`admin_actions.update_course`) — un re-scrape n'a pas à dupliquer cette
capacité, et FR-004 est corrigée en ce sens ci-dessous.

---

### User Story 2 - Rejouer un import qui avait échoué (Priority: P2)

Un import précédent (initial ou re-scrape) s'est arrêté en erreur pour une
partie des participants (site source temporairement indisponible, format
inattendu…). L'administrateur relance un re-scrape sur la même course pour
compléter les résultats manquants, sans devoir supprimer et réimporter
l'épreuve à la main.

**Why this priority**: Second cas d'usage nommé dans le besoin, moins fréquent
que le rafraîchissement de routine mais sans lequel un import partiel reste
bloqué faute d'un accès CLI.

**Independent Test**: Peut être testé seul en simulant un import partiel puis
en relançant le re-scrape sur la même course et en constatant que les
participants manquants apparaissent.

**Acceptance Scenarios**:

1. **Given** une course dont l'import précédent n'a rapatrié qu'une partie des
   participants, **When** l'administrateur déclenche un re-scrape,
   **Then** les participants manquants sont ajoutés sans dupliquer ceux déjà
   présents.

---

### User Story 3 - Empêcher deux re-scrapes concurrents sur la même course (Priority: P3)

Un administrateur ouvre deux onglets sur la même course, ou un collègue
déclenche un re-scrape pendant qu'un premier est encore en cours. Le second
déclenchement est refusé plutôt que de lancer un second scrape en parallèle
sur la même course.

**Why this priority**: Protège l'intégrité du classement (deux scrapes
concurrents écrivant sur la même course) ; priorité plus basse car c'est un
cas de bord, pas le chemin nominal.

**Independent Test**: Peut être testé seul en déclenchant un re-scrape puis en
tentant d'en déclencher un second sur la même course avant la fin du premier,
et en vérifiant le refus explicite.

**Acceptance Scenarios**:

1. **Given** un re-scrape déjà en cours sur une course, **When** un second
   déclenchement est tenté sur la **même** course, **Then** il est refusé avec
   un message explicite plutôt que silencieusement ignoré ou mis en file.
2. **Given** un re-scrape en cours sur une course A, **When** un
   administrateur déclenche un re-scrape sur une course B différente,
   **Then** le second se déroule normalement — le refus ne porte que sur la
   même course.

### Edge Cases

- Le chronométreur source est injoignable pendant le re-scrape : l'opération
  se termine en échec explicite, la course conserve son classement précédent
  intact (aucune perte de données déjà en base).
- Le scrape rapatrie zéro participant (page source vidée, erreur de format) :
  refusé plutôt qu'appliqué — un classement existant ne doit jamais être
  remplacé par un résultat vide.
- Le re-scrape fait apparaître une épreuve différente de celle attendue (nom,
  date ou type ne correspondent plus à ce que la source publiait) : refusé, la
  course visée n'est pas modifiée.
- Un administrateur ferme l'onglet ou perd la connexion pendant qu'un
  re-scrape est en cours : l'opération continue côté serveur jusqu'à son
  terme ; rouvrir la page course affiche l'état à jour.
- Un athlète change de dossard entre deux imports (réconciliation d'identité) :
  les fiches devenues orphelines de cette course sont nettoyées en fin de
  re-scrape, comme le fait déjà la CLI `rescrape-db`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un administrateur habilité de
  déclencher un re-scrape sur une course déjà en base, depuis la page de
  cette course.
- **FR-002**: Le système DOIT afficher la progression du re-scrape en temps
  réel, sans que l'administrateur ait à recharger la page manuellement.
- **FR-003**: Le déclenchement DOIT court-circuiter toute fraîcheur mise en
  cache — un re-scrape demandé explicitement doit toujours interroger la
  source, même si la course a été importée récemment.
- ~~**FR-004**: Le système DOIT mettre à jour les métadonnées de la course
  (nom, date, type d'épreuve) si elles ont changé chez le chronométreur.~~
  **Retirée** (revue de code, post-implémentation) — incompatible avec FR-009 :
  l'identité (nom, date, type) est ce que FR-009 refuse de voir diverger, elle
  ne peut donc jamais être « mise à jour » par ce chemin. Corriger un libellé
  reste `PATCH /admin/courses/{id}` (`courses:write`, #117), un geste distinct
  et déjà existant. Voir l'amendement sous User Story 1, Acceptance Scenario 3.
- **FR-005**: Le système DOIT mettre à jour les participations existantes et
  ajouter les nouvelles, sans dupliquer un participant déjà présent (un même
  dossard reste une seule ligne).
- **FR-006**: Le système DOIT nettoyer, en fin de re-scrape, les fiches
  coureur devenues orphelines de cette course par réconciliation d'identité
  (même règle que le rafraîchissement en ligne de commande).
- **FR-007**: Le système DOIT refuser un second re-scrape déclenché sur une
  course pendant qu'un premier y est déjà en cours, avec un message explicite.
- **FR-008**: Le système DOIT réutiliser, pour la progression, le même
  mécanisme de suivi que celui de la bascule de source active — aucun second
  mécanisme de progression ne doit être introduit pour cette feature.
- **FR-009**: Le système DOIT refuser d'appliquer un résultat de re-scrape qui
  ne rapatrie aucun participant, ou dont l'identité de l'épreuve (nom, date,
  type) diverge de la course visée — dans les deux cas, la course visée
  conserve son état précédent intact.
- **FR-010**: Seul un administrateur habilité (le même pouvoir que la bascule
  de source active) DOIT pouvoir déclencher un re-scrape ; un utilisateur non
  habilité ou anonyme en est empêché.
- **FR-011**: Le système DOIT continuer et terminer un re-scrape déjà démarré
  même si l'administrateur qui l'a déclenché quitte la page ou perd sa
  connexion.

### Key Entities

- **Course**: épreuve déjà en base, cible du re-scrape ; porte nom, date,
  type, et la source active dont l'URL est réinterrogée.
- **Participation**: résultat d'un athlète sur la course, identifié par son
  dossard ; mis à jour ou créé par le re-scrape, jamais dupliqué.
- **Fiche coureur (Athlete)**: peut devenir orpheline d'une course si la
  réconciliation d'identité du re-scrape la rattache ailleurs ; nettoyée en
  fin d'opération si elle ne porte plus aucune participation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur peut rafraîchir une course depuis le
  back-office sans aucune commande technique, du clic jusqu'à la confirmation
  de fin.
- **SC-002**: La progression du re-scrape reste visible et se met à jour sans
  action de l'administrateur pendant toute la durée de l'opération.
- **SC-003**: Une course dont les résultats source ont changé affiche des
  données à jour immédiatement après la fin d'un re-scrape déclenché depuis le
  back-office, dans 100 % des cas de succès.
- **SC-004**: Un re-scrape qui échoue (source injoignable, résultat vide,
  épreuve divergente) laisse le classement existant intact, sans exception.
- **SC-005**: Deux re-scrapes déclenchés sur la même course ne s'exécutent
  jamais en parallèle.

## Assumptions

- Le pouvoir d'administration exigé pour déclencher un re-scrape est le même
  que celui qui gouverne déjà la bascule de source active sur une course
  (`courses:sources`) — c'est le geste voisin le plus proche, et #275 a déjà
  tranché que les deux partagent leur mécanisme de progression.
- La logique de scrape et d'import elle-même (mapping, upsert par dossard,
  réconciliation d'identité, purge des orphelins) est celle déjà en place pour
  le rafraîchissement en ligne de commande (`rescrape-db`) ; cette feature
  n'en change pas les règles, elle ajoute un déclencheur depuis le
  back-office.
- Les dépendances d'authentification et de RBAC (#115, #116) sont déjà en
  place ; cette feature n'a rien à y ajouter.
- Le re-scrape porte sur la source **active** de la course — changer la
  source interrogée est un geste distinct (bascule de source, #285), pas le
  périmètre de cette feature.
