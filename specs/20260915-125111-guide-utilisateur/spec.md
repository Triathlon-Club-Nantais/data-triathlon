# Feature Specification: Guide utilisateur intégré

**Feature Branch**: `865-guide-utilisateur`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Issue GitHub #865 — feat(frontend): guide utilisateur intégré couvrant toutes les fonctionnalités.

Constat de départ : aucun guide utilisateur n'existe dans l'application. Les fonctionnalités (dashboard, club, résultats, comparaison, ajout de résultat, carte, bénévolat côté membres ; fournisseurs, doublons, droits, quality, batches, groupes, utilisateurs, journal, maintenance, retours-utilisateurs, variantes-club, portée-compteurs côté admin) ne sont documentées nulle part de façon accessible depuis l'app.

Demande :
- Guide utilisateur accessible via une ou plusieurs pages dans l'application (pas un lien externe).
- Couvre l'ensemble des fonctionnalités membres ET admin listées ci-dessus.
- Facilement visible (accessible en un clic depuis la navigation principale et/ou l'admin).
- Très concis sur les instructions (étapes courtes, pas de pavés de texte).
- Chaque section couvre le ou les cas d'usage réels, pas seulement une description d'interface.
- Chaque section illustrée d'au moins une capture d'écran à jour — indispensable à la qualité, non optionnel.
- Contenu en français.

Hors périmètre : pas de doc technique (API/architecture), pas de vidéo/multimédia hors captures d'écran, pas de traduction."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un membre découvre les fonctionnalités du club (Priority: P1)

Un membre du club, nouveau ou existant, veut comprendre comment utiliser le dashboard, consulter son club, voir ses résultats, comparer ses performances, ajouter un résultat manquant, ou déclarer du bénévolat. Il ouvre le guide depuis la navigation principale et trouve directement la section correspondant à ce qu'il veut faire.

**Why this priority**: C'est l'audience la plus large (tous les membres) et le problème le plus fréquemment rencontré (découverte de l'app sans accompagnement).

**Independent Test**: Peut être testé en ouvrant le guide, en naviguant vers chacune des 6 sections membres (dashboard, club, résultats, comparaison, ajout de résultat, bénévolat), et en vérifiant que chacune répond à un cas d'usage concret avec une capture d'écran à jour.

**Acceptance Scenarios**:

1. **Given** un membre connecté sur n'importe quelle page de l'application, **When** il clique sur l'accès au guide depuis la navigation principale, **Then** le guide s'affiche avec la liste des sections membres.
2. **Given** le guide ouvert, **When** le membre sélectionne la section "ajouter un résultat", **Then** il voit les étapes concises pour le faire, illustrées d'au moins une capture d'écran à jour.
3. **Given** un membre sans droits admin, **When** il consulte le guide, **Then** il ne voit que les sections membres, pas les sections admin.

---

### User Story 2 - Un administrateur découvre les outils de back-office (Priority: P2)

Un utilisateur avec des droits admin veut comprendre comment gérer les épreuves, gérer les fournisseurs, résoudre des doublons, gérer les droits d'accès, suivre la qualité des données, lancer des batches, gérer les groupes/utilisateurs, consulter le journal, effectuer une opération de maintenance, traiter les retours utilisateurs, gérer les variantes de club, configurer la portée des compteurs, valider les déclarations de bénévolat, ou gérer les accès au back-office. Il ouvre le guide depuis l'admin et trouve la section correspondante.

**Why this priority**: Audience plus restreinte (admins uniquement) mais fonctionnalités plus nombreuses et plus complexes à découvrir seul, avec un risque d'erreur plus élevé si mal utilisées.

**Independent Test**: Peut être testé en se connectant avec un compte admin, en ouvrant le guide depuis l'admin, et en vérifiant que chacune des 15 fonctionnalités admin listées dispose d'une section avec cas d'usage et capture d'écran.

**Acceptance Scenarios**:

1. **Given** un utilisateur avec droits admin, **When** il ouvre le guide depuis l'espace admin, **Then** il voit en plus des sections membres les sections admin (épreuves, fournisseurs, doublons, droits, quality, batches, groupes, utilisateurs, journal, maintenance, retours-utilisateurs, variantes-club, portée-compteurs, validation du bénévolat, accès au back-office).
2. **Given** le guide ouvert côté admin, **When** l'admin sélectionne la section "doublons", **Then** il voit les étapes concises du cas d'usage (identifier et résoudre un doublon), illustrées d'une capture d'écran à jour.

---

### User Story 3 - N'importe quel utilisateur retrouve rapidement une section précise (Priority: P3)

Un utilisateur qui a déjà consulté le guide une fois revient plus tard pour une question précise (ex. "comment déclarer du bénévolat ?") et veut atteindre directement la section concernée sans reparcourir tout le guide.

**Why this priority**: Améliore l'usage répété du guide une fois les deux premières user stories livrées, mais n'est pas bloquant pour une première version utile.

**Independent Test**: Peut être testé en accédant directement à l'URL d'une section précise du guide (lien partageable) et en vérifiant qu'elle s'affiche seule, sans dépendre d'une navigation préalable dans les autres sections.

**Acceptance Scenarios**:

1. **Given** un utilisateur ayant le lien direct vers une section du guide, **When** il ouvre ce lien, **Then** la section s'affiche directement sans étape intermédiaire.

---

### Edge Cases

- Que voit un membre sans droits admin qui tente d'accéder directement (par URL) à une section admin du guide ?
- Que se passe-t-il si une capture d'écran référencée par une section devient obsolète après une évolution de l'interface (aucune détection automatique n'est demandée dans ce périmètre, mais l'absence d'image ne doit jamais casser l'affichage de la section) ?
- Comment le guide se comporte-t-il sur un écran mobile (largeur réduite) ?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT exposer un guide utilisateur sous forme de pages dédiées dans l'application (routes internes), sans dépendre d'un lien vers une documentation externe.
- **FR-002**: Le guide DOIT être accessible en un clic depuis la navigation principale pour tout utilisateur connecté.
- **FR-003**: Le guide DOIT également être accessible en un clic depuis l'espace admin pour les utilisateurs ayant des droits admin.
- **FR-004**: Le guide DOIT comporter une section dédiée à chacune des fonctionnalités membres suivantes : dashboard, club, résultats, comparaison, ajout de résultat, bénévolat.
- **FR-005**: Le guide DOIT comporter une section dédiée à chacune des fonctionnalités admin suivantes, visibles uniquement aux utilisateurs ayant les droits admin : épreuves, fournisseurs, doublons, droits, quality, batches, groupes, utilisateurs, journal, maintenance, retours-utilisateurs, variantes-club, portée-compteurs, validation du bénévolat, accès au back-office.
- **FR-006**: Chaque section DOIT présenter des instructions concises, sous forme d'étapes courtes, sans pavé de texte.
- **FR-007**: Chaque section DOIT inclure au moins une capture d'écran à jour illustrant la fonctionnalité décrite.
- **FR-008**: Chaque section DOIT décrire le ou les cas d'usage réels de la fonctionnalité (ce que l'utilisateur cherche à accomplir), pas uniquement une description statique de l'interface.
- **FR-009**: Le contenu du guide DOIT être rédigé en français.
- **FR-010**: Chaque section DOIT être atteignable directement (URL propre), sans devoir reparcourir les autres sections.
- **FR-011**: Le système NE DOIT PAS afficher les sections admin du guide à un utilisateur sans droits admin, y compris par accès direct à l'URL de la section.

### Key Entities

- **Section de guide** : une fonctionnalité de l'application documentée (titre, étapes concises, cas d'usage, une ou plusieurs captures d'écran, audience membre ou admin).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Chacune des 21 fonctionnalités listées (6 membres + 15 admin) dispose d'une section dédiée avec au moins une capture d'écran à jour.
- **SC-002**: Le guide est atteignable en un clic depuis n'importe quelle page de l'application pour un membre, et depuis n'importe quelle page admin pour un admin.
- **SC-003**: Un utilisateur testé trouve la section répondant à une question fonctionnelle courante (ex. "comment déclarer du bénévolat ?") en moins de 2 minutes.
- **SC-004**: Aucune section du guide ne dépasse l'équivalent d'un écran de lecture sans défilement excessif (contenu concis, pas de pavés de texte).
- **SC-005**: Un utilisateur sans droits admin ne peut voir aucune section admin, ni via la navigation ni via un accès direct par URL.

## Assumptions

- Les captures d'écran sont des fichiers image statiques intégrés au guide (pas de génération dynamique en temps réel).
- La visibilité des sections admin réutilise le système d'autorisation déjà en place pour les pages admin existantes, sans nouveau mécanisme de permission.
- Le guide est réservé aux utilisateurs connectés (membres et admins), cohérent avec le fait que l'application est un espace de club restreint.
- La maintenance des captures d'écran suite à une évolution future de l'interface est un effort continu qui n'est pas résolu par cette livraison (pas de détection automatique d'obsolescence demandée).
- La fonctionnalité « carte » est exclue du guide pour cette livraison : elle reste masquée de la navigation (`soon`, réservée à `pages:preview`) et n'est pas encore ouverte au grand public — documenter une fonctionnalité non lancée dans le guide public la révélerait avant son heure. Elle entrera dans le guide quand son statut `soon` sera levé.
- Le périmètre admin de FR-005/SC-001 couvre l'inventaire réel des écrans `/admin` (hors ceux encore `soon`, ex. « Feature flags ») au moment de la rédaction de cette spec, pas seulement les 12 fonctionnalités énumérées dans l'issue #865 d'origine — 3 écrans existants en avaient été omis (Épreuves, validation du bénévolat, Accès au back-office).
