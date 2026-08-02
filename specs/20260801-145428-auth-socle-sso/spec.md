# Feature Specification: Socle d'authentification SSO pour le back-office admin

**Feature Branch**: `20260801-145428-auth-socle-sso`

**Created**: 2026-08-01

**Status**: Draft

**Input**: Issue #114 (épique #81), en remplacement de la PR #159. Périmètre élargi et assumé :
backend **et** frontend dans la même livraison — l'UI de connexion de l'issue #116 est couverte ici.

**Sondage faisant autorité** : `docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md`.
Il **prime** sur cette spec. Toute divergence se tranche en re-sondant.

---

## Clarifications

### Session 2026-08-02

- Q: Le modèle de données livré ici doit-il garantir qu'un rôle **rattaché à une organisation** pourra être ajouté plus tard sans restructuration destructive ? → A: Oui, comme exigence de compatibilité seule (FR-041, SC-014) — aucune entité Organisation ni Rôle n'est créée dans cette livraison.
- Q: Un refus de connexion peut-il indiquer explicitement que l'adresse n'est pas dans la liste des comptes autorisés ? → A: Oui. FR-030 est recentrée sur ce qu'elle protège réellement — ne pas révéler qu'une adresse est **déjà enregistrée** — l'énumération d'adresses tierces étant impossible en SSO, où seule l'adresse certifiée pour son propre compte peut être soumise. Le code `account_not_allowed` est conservé.
- Q: Comment un administrateur doit-il pouvoir fermer d'un coup toutes les sessions d'un compte, ou toutes celles de tous les comptes ? → A: Par une **procédure documentée**, sans outil dédié (FR-016 reformulée) : désactivation du compte pour un utilisateur, suppression de toutes les sessions enregistrées pour la totalité. La documentation doit signaler qu'une rotation de la clé de signature ne ferme aucune session.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Un contributeur du club ouvre une session (Priority: P1)

Un contributeur autorisé arrive sur le site, clique sur « Se connecter », choisit le moyen de
connexion proposé, s'authentifie chez le fournisseur d'identité, et revient sur le site connecté.
Son nom apparaît dans un menu utilisateur, d'où il peut se déconnecter. Sa session survit à un
rafraîchissement de page et à la fermeture de l'onglet.

**Why this priority**: c'est le socle. Les issues #115 (rôles), #117, #118 et #119 en dépendent
toutes, et aucune valeur n'est livrable sans lui.

**Independent Test**: se connecter dans un navigateur, vérifier que l'utilisateur apparaît, se
déconnecter, vérifier que l'accès authentifié est refermé. Testable de bout en bout sans aucune
autre partie de l'épique.

**Acceptance Scenarios**:

1. **Given** un visiteur anonyme dont l'adresse figure dans la liste des comptes autorisés,
   **When** il déroule le parcours de connexion jusqu'au bout,
   **Then** une session est ouverte, son identité est visible, et un utilisateur est enregistré.
2. **Given** un contributeur déjà connu du système,
   **When** il se reconnecte,
   **Then** aucun nouvel utilisateur n'est créé et son adresse est rafraîchie si elle a changé
   chez le fournisseur.
3. **Given** un utilisateur connecté,
   **When** il rafraîchit la page ou rouvre le site dans un nouvel onglet,
   **Then** il est toujours connecté.
4. **Given** un utilisateur connecté,
   **When** il se déconnecte,
   **Then** sa session cesse immédiatement d'être acceptée, et **seule** cette session est
   fermée — ses autres appareils restent connectés.
5. **Given** un utilisateur dont la session a expiré,
   **When** il sollicite une ressource authentifiée,
   **Then** l'accès est refusé et il est invité à se reconnecter.

---

### User Story 2 — Le site public reste intégralement accessible sans compte (Priority: P1)

Un visiteur anonyme continue de consulter les résultats, les athlètes, les courses, la carte, le
tableau de bord, et d'ajouter une épreuve, exactement comme avant. Rien de ce qui existait n'exige
de session.

**Why this priority**: c'est la contrainte produit structurante de l'épique #81, et une régression
y serait invisible en développement mais totale en production.

**Independent Test**: dérouler l'intégralité des parcours publics existants sans jamais se
connecter, avant et après la livraison, et constater l'identité des comportements.

**Acceptance Scenarios**:

1. **Given** un visiteur sans session, **When** il consulte n'importe quelle ressource publique
   existante, **Then** elle répond comme avant la livraison.
2. **Given** un visiteur sans session, **When** il ajoute une épreuve par le formulaire public,
   **Then** l'import se déroule comme avant.
3. **Given** une installation où l'authentification n'est pas configurée, **When** un visiteur
   utilise le site, **Then** tout le site public fonctionne et seul l'accès au parcours de
   connexion signale que l'authentification est indisponible.

---

### User Story 3 — Les tentatives de connexion illégitimes sont refusées lisiblement (Priority: P2)

Une personne dont l'adresse ne figure pas dans la liste des comptes autorisés, ou dont le
fournisseur ne certifie pas l'adresse, ou dont le parcours a été altéré en chemin, est refusée.
Elle voit un message français compréhensible sur la page de connexion, jamais une page technique
brute.

**Why this priority**: sans ce garde-fou, le premier rôle posé en #115 s'appliquerait à une table
d'utilisateurs ouverte à tous. La lisibilité du refus est un besoin d'exploitation autant que
d'ergonomie.

**Independent Test**: dérouler chaque cas de refus et vérifier le message affiché et l'absence de
session ouverte.

**Acceptance Scenarios**:

1. **Given** une personne non autorisée, **When** elle achève le parcours chez le fournisseur,
   **Then** aucune session n'est ouverte, **aucun utilisateur n'est enregistré**, et la page de
   connexion affiche un refus en français.
2. **Given** un fournisseur qui ne certifie pas l'adresse de la personne, **When** le parcours
   revient, **Then** la connexion est refusée avant même l'examen de la liste d'autorisation.
3. **Given** un retour de parcours dont la preuve d'origine est absente, altérée, expirée, déjà
   consommée, ou émise pour un autre moyen de connexion, **Then** la connexion est refusée.
4. **Given** l'un quelconque de ces refus, **Then** la personne atterrit sur la page de connexion
   avec un message français, et **jamais** sur une page de données techniques.
5. **Given** la personne refusée, **When** elle recommence un parcours légitime,
   **Then** rien de l'échec précédent ne subsiste pour l'en empêcher.

---

### Edge Cases

- **Le fournisseur d'identité est injoignable ou répond en erreur** : la connexion échoue avec un
  message français, aucune session n'est ouverte, et le site public n'est pas affecté.
- **La personne abandonne chez le fournisseur** (refus d'autorisation) : retour propre à la page
  de connexion, sans trace résiduelle.
- **La personne revient sur un retour de parcours périmé** (au-delà de la fenêtre de validité) :
  refus, et invitation à recommencer.
- **Deux personnes différentes portent la même adresse chez deux fournisseurs différents** : ce
  sont **deux utilisateurs distincts**. L'adresse n'apparie jamais deux identités.
- **La personne change d'adresse chez son fournisseur** : elle reste le même utilisateur ; son
  adresse est mise à jour. Si sa nouvelle adresse n'est plus autorisée, sa prochaine connexion est
  refusée, ses sessions en cours restant valides jusqu'à leur terme.
- **Un compte est désactivé alors que des sessions sont ouvertes** : ces sessions cessent
  immédiatement d'être acceptées.
- **L'authentification n'est pas configurée** (secrets absents) : aucun moyen de connexion n'est
  proposé, le parcours signale l'indisponibilité, et le site public est intact.
- **La liste des comptes autorisés est vide** : aucune connexion n'est possible. L'absence de
  configuration ne vaut jamais autorisation générale.
- **Le fournisseur ne rend aucune adresse certifiée** : refus explicite.
- **Deux onglets démarrent un parcours simultanément** : le second parcours abouti est celui qui
  compte ; le premier échoue proprement, sans effet de bord.
- **Un retour de parcours est rejoué à l'identique** : le second rejeu est refusé.

---

## Requirements *(mandatory)*

### Exigences fonctionnelles — identité et comptes

- **FR-001**: Le système DOIT permettre d'ouvrir une session par délégation à un fournisseur
  d'identité externe, sans jamais détenir le mot de passe de la personne.
- **FR-002**: Le système DOIT identifier une identité externe par le **couple (moyen de connexion,
  identifiant opaque du fournisseur)**, et par rien d'autre.
- **FR-003**: L'adresse électronique NE DOIT JAMAIS servir de clé d'appariement. Une identité
  externe inconnue crée **toujours** un nouvel utilisateur, même si l'adresse est déjà connue du
  système.
- **FR-004**: Le système NE DOIT PAS rattacher automatiquement deux identités externes au même
  utilisateur. Aucun mécanisme de liaison de comptes n'est livré.
- **FR-005**: Le système DOIT refuser une identité dont le fournisseur ne certifie pas l'adresse,
  et ce refus DOIT intervenir **avant** l'examen de la liste des comptes autorisés.
- **FR-006**: Le système DOIT refuser toute identité dont l'adresse certifiée ne figure pas dans
  la liste des comptes autorisés, **sans enregistrer d'utilisateur**.
- **FR-007**: Une liste de comptes autorisés vide DOIT interdire toute connexion, et aucun moyen
  de connexion NE DOIT être proposé dans ce cas.
- **FR-008**: À chaque connexion d'une identité déjà connue, le système DOIT rafraîchir les
  attributs mutables issus du fournisseur sans créer de doublon.
- **FR-009**: Le système NE DOIT conserver aucun jeton d'accès délivré par le fournisseur au-delà
  du parcours de connexion.
- **FR-010**: Le modèle DOIT permettre qu'un utilisateur porte **plusieurs** moyens de connexion,
  chacun révocable indépendamment, sans restructuration ultérieure.

### Exigences fonctionnelles — session

- **FR-011**: Le système DOIT porter la session par une valeur **opaque et imprévisible**, sans
  aucune information sur l'utilisateur.
- **FR-012**: Le système NE DOIT PAS conserver cette valeur en clair. Sa divulgation depuis le
  stockage NE DOIT PAS permettre d'usurper une session.
- **FR-013**: Une session DOIT être acceptée **si et seulement si** elle existe, n'a pas expiré,
  **et** que le compte associé est actif. Ces trois conditions sont un invariant vérifié.
- **FR-014**: La déconnexion DOIT mettre fin **à cette session seule** et DOIT être sans effet ni
  erreur si aucune session n'est présente.
- **FR-015**: La désactivation d'un compte DOIT mettre fin immédiatement à toutes ses sessions.
- **FR-016**: La fermeture en masse des sessions DOIT être **documentée comme procédure
  d'exploitation** ; aucun outil dédié n'est livré. Pour **un compte**, la désactivation (FR-015)
  ferme déjà immédiatement toutes ses sessions. Pour **tous les comptes**, la procédure est la
  suppression de toutes les sessions enregistrées. Cette documentation DOIT signaler qu'une
  rotation de la clé de signature **ne ferme aucune session** : le jeton de session est opaque et
  vérifié en base, il n'est pas signé — s'attendre à l'inverse serait croire une fuite colmatée
  alors qu'elle ne l'est pas.
- **FR-017**: La valeur de session NE DOIT PAS être exposée au code s'exécutant dans le navigateur.
- **FR-018**: Les réponses portant une identité NE DOIVENT JAMAIS pouvoir être servies par un cache
  intermédiaire à un autre visiteur.
- **FR-019**: Le système DOIT supprimer opportunément les sessions expirées, sans dépendre d'un
  ordonnanceur — le dépôt n'en possède aucun.

### Exigences fonctionnelles — intégrité du parcours

- **FR-020**: Le système DOIT vérifier qu'un retour de parcours correspond à un parcours qu'il a
  lui-même initié depuis le même navigateur.
- **FR-021**: Cette preuve d'origine DOIT être infalsifiable, avoir une durée de vie courte, et
  désigner explicitement le **moyen de connexion** pour lequel elle a été émise.
- **FR-022**: Un retour de parcours DOIT être refusé si la preuve est absente, altérée, expirée,
  déjà consommée, ou émise pour un autre moyen de connexion.
- **FR-023**: La preuve DOIT être consommée **avant** tout échange avec le fournisseur, et
  effacée sur **tous** les chemins de sortie du retour de parcours, succès compris.
- **FR-024**: Le système DOIT lier le retour de parcours au navigateur qui l'a initié, par un
  secret que l'interception de l'URL de retour ne suffit pas à obtenir.
- **FR-025**: Toute validation locale DOIT précéder le premier échange réseau avec le fournisseur.
- **FR-026**: La destination de redirection après connexion DOIT être fixée par la configuration.
  Le système NE DOIT JAMAIS accepter de destination fournie en paramètre d'entrée.

### Exigences fonctionnelles — restitution des erreurs

- **FR-027**: Tout échec du retour de parcours DOIT ramener la personne sur la page de connexion.
  Le système NE DOIT JAMAIS afficher de page de données techniques dans le navigateur.
- **FR-028**: La cause DOIT être transmise sous forme d'un **code appartenant à un ensemble fermé**,
  jamais un message provenant du fournisseur ni une donnée d'entrée.
- **FR-029**: L'interface DOIT traduire ces codes en messages **français**.
- **FR-030**: Le système NE DOIT PAS révéler, dans ses refus, qu'une adresse est **déjà
  enregistrée** : aucun refus ne distingue une personne déjà connue du système d'une inconnue.
  Un refus PEUT en revanche indiquer que l'adresse n'est **pas autorisée**. La protection contre
  l'énumération de comptes, qui motive cette exigence, ne s'applique pas à ce second cas :
  contrairement à un formulaire adresse/mot de passe, une personne ne peut soumettre que l'adresse
  que le fournisseur **certifie pour son propre compte**, donc aucune adresse tierce n'est
  testable.

### Exigences fonctionnelles — extensibilité

- **FR-031**: Le système DOIT exposer les moyens de connexion **effectivement disponibles**, et
  l'interface DOIT s'en servir pour construire l'écran de connexion. Aucune liste de moyens de
  connexion NE DOIT être codée en dur dans l'interface.
- **FR-032**: Le contrat interne d'un moyen de connexion NE DOIT PAS énumérer les mécanismes
  propres à un fournisseur. Les éléments qu'un fournisseur doit retrouver au retour du parcours
  DOIVENT être transportés de façon **opaque** pour le reste du système.
- **FR-033**: L'ajout d'un fournisseur NE DOIT exiger la modification ni du contrat, ni du flux, ni
  d'un fournisseur existant.
- **FR-034**: **Un seul** fournisseur est livré en production : GitHub. Toute doublure de test NE
  DOIT PAS être atteignable en production, et cette inaccessibilité DOIT être vérifiée.
- **FR-041**: Le rôle livré ultérieurement par #115 NE DOIT PAS être porté par l'entité
  **Utilisateur** elle-même : il DOIT l'être par une **association entre un utilisateur et une
  organisation**, le rôle étant relatif à un club et jamais global à l'application. Le modèle
  livré ici DOIT permettre d'ajouter cette association **sans restructuration destructive** —
  c'est-à-dire sans qu'aucune entité livrée ne doive être supprimée, ni aucun de ses attributs
  réécrit ou déplacé. Aucune entité Organisation ni Rôle N'EST créée par cette livraison.

### Exigences fonctionnelles — non-régression et exploitation

- **FR-035**: Aucune ressource publique existante NE DOIT exiger de session. Cette propriété DOIT
  être vérifiée pour l'ensemble des ressources existantes.
- **FR-036**: Une authentification non configurée NE DOIT PAS empêcher le site public de
  fonctionner ; le parcours de connexion DOIT alors signaler l'indisponibilité par un message
  **français**.
- **FR-037**: Les secrets NE DOIVENT JAMAIS être versionnés, et le système DOIT refuser une clé de
  signature trop faible.
- **FR-038**: Le système NE DOIT JAMAIS journaliser un secret, un jeton, ni les paramètres du
  retour de parcours.
- **FR-039**: **Toute** sortie réseau du parcours DOIT traverser le contrôle de destination
  existant du projet (#101). Cette propriété DOIT être garantie par l'unique garde automatique
  déjà en place, **étendu** — jamais par un second garde parallèle.
- **FR-040**: L'accès aux écrans d'administration DOIT être refusé sans session et rediriger vers
  la connexion. Cette garde est **d'interface seulement** : les ressources d'administration
  restent ouvertes, conformément à FR-035, et cela DOIT être documenté sans ambiguïté.

### Key Entities

- **Utilisateur** : la personne côté application. Porte son adresse de contact, son état d'activité,
  sa date de création, et un rattachement facultatif à une fiche d'athlète. **Ne porte pas le
  rôle** : celui-ci sera rattaché à un couple (utilisateur, organisation) par #115, hors de cette
  entité, conformément à FR-041.
- **Identité** : un moyen de se connecter à un utilisateur. Porte le moyen de connexion,
  l'identifiant opaque chez le fournisseur, l'adresse constatée, et — pour un futur mot de passe —
  un secret vérifiable. Unique par couple (moyen de connexion, identifiant). Plusieurs identités
  peuvent pointer un même utilisateur ; aucune n'est créée automatiquement à partir d'une autre.
- **Session** : la preuve qu'un navigateur agit pour un utilisateur. Porte l'empreinte de sa valeur
  opaque, sa date d'expiration et sa date de création. Sa suppression met fin à l'accès.
- **Moyen de connexion** : ce qui est proposé sur l'écran de connexion. Porte un identifiant court
  et un libellé d'affichage, et n'est proposé que s'il est configuré.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **100 %** des parcours publics existants fonctionnent sans session, avant comme après
  la livraison — vérifié par une suite dédiée couvrant chaque ressource publique.
- **SC-002**: Un contributeur autorisé ouvre une session en **moins de 30 secondes** et en **au
  plus trois interactions** depuis la page d'accueil.
- **SC-003**: **100 %** des tentatives non autorisées sont refusées **sans laisser d'utilisateur
  enregistré**.
- **SC-004**: **100 %** des retours de parcours dont la preuve d'origine est absente, altérée,
  expirée, rejouée ou destinée à un autre moyen de connexion sont refusés.
- **SC-005**: **Aucun** échec du parcours n'aboutit à l'affichage d'une page de données techniques ;
  **100 %** ramènent à la page de connexion avec un message français.
- **SC-006**: Une déconnexion rend la session inutilisable **immédiatement**, et n'affecte **aucune**
  autre session du même utilisateur.
- **SC-007**: La désactivation d'un compte rend **toutes** ses sessions inutilisables immédiatement.
- **SC-008**: **Aucune** valeur de session exploitable n'est retrouvable dans le stockage.
- **SC-009**: **Aucune** sortie réseau du parcours n'échappe au contrôle de destination — vérifié
  par le garde automatique du dépôt, étendu à cet effet.
- **SC-010**: L'écran de connexion reflète **exactement** les moyens de connexion disponibles, y
  compris quand il n'y en a aucun ; aucun moyen n'y est codé en dur.
- **SC-011**: Ajouter un second fournisseur ne demande **aucune** modification du contrat, du flux,
  ni du fournisseur existant — vérifié en faisant dérouler le parcours complet à une doublure.
- **SC-012**: La doublure de test est **inatteignable** en production — vérifié par un test sur le
  registre chargé à froid.
- **SC-013**: La suite de tests s'exécute **sans aucun accès réseau** et **sans dépendre** de la
  configuration locale du développeur.
- **SC-014**: L'entité Utilisateur livrée ne porte **aucun** attribut de rôle, et l'ajout ultérieur
  d'une association (utilisateur, organisation, rôle) n'exige la suppression ni la réécriture
  d'**aucune** entité livrée — vérifié à la revue du modèle de données.

---

## Assumptions

- **Les contributeurs du back-office possèdent tous un compte GitHub.** C'est ce qui rend
  acceptable de ne livrer que ce fournisseur, et ce qui reporte le mot de passe hors périmètre.
- **La liste des comptes autorisés est maintenue à la main** par un administrateur, via la
  configuration de déploiement. Il n'existe pas d'écran de gestion des comptes — c'est le
  périmètre de #115 et #117.
- **Les rôles ne sont pas livrés.** Tout utilisateur authentifié a exactement les mêmes droits, à
  savoir ceux d'un visiteur anonyme, puisque aucune ressource n'est protégée (FR-035). La garde
  des écrans d'administration est cosmétique et documentée comme telle (FR-040). Seule leur
  **forme future** est contrainte, par FR-041 : le rôle sera relatif à une organisation.
- **L'organisation n'existe pas encore comme entité**, et n'est pas créée ici. FR-041 ne pose
  qu'une contrainte de non-régression sur le modèle : il interdit une forme de rôle qu'il faudrait
  défaire, il n'anticipe aucune structure. Le multi-club reste un horizon, pas une livraison.
- **L'interface parle au backend par le même domaine**, via la réindirection déjà en place. La
  destination du retour de parcours vise donc le domaine de l'interface, jamais celui de l'API —
  c'est la leçon retenue de la PR #159.
- **L'authentification n'est utilisable que depuis l'espace de travail principal en développement**,
  le port de l'interface n'y étant ni fixé ni publié, et un fournisseur n'acceptant qu'une seule
  adresse de retour. Ce piège est documenté plutôt que corrigé — le corriger relèverait de
  l'outillage de développement, hors périmètre.
- **Le rattachement d'un utilisateur à une fiche d'athlète est prévu mais non exploité** ici.
- **La pseudo-identité existante de l'interface** (« Sélectionner mon nom ») subsiste et coexiste
  avec la session. Les réconcilier relève de #117.
- **La durée de session par défaut est de 7 jours**, sans prolongation glissante, reprise de la
  PR #159.
- **Aucune limitation de débit n'est livrée.** Le risque est identifié (le parcours de retour est
  coûteux et le nombre de traitements simultanés est borné) et réduit par FR-025 ; une limitation
  en bonne et due forme relève d'un ticket d'exploitation dédié.

---

## Hors périmètre

- Les rôles et la protection des ressources d'administration (#115) — la **fonctionnalité** ; la
  contrainte de forme sur le modèle, elle, est posée ici par FR-041.
- Les écrans d'administration eux-mêmes (#117, #118, #119).
- La connexion par adresse et mot de passe, et tout ce qu'elle entraîne : réinitialisation,
  vérification d'adresse, verrouillage après échecs. Le modèle l'accueille ; la fonctionnalité
  n'est pas livrée.
- Un second fournisseur en production.
- La liaison de plusieurs identités à un même utilisateur.
- L'écran de gestion des sessions actives.
- Le journal d'audit formel.
- La limitation de débit.
