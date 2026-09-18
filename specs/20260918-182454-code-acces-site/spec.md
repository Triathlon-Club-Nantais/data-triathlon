# Feature Specification: Code d'accès du site : affichage en clair, reword, validité 3 mois

**Feature Branch**: `20260918-182454-code-acces-site`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Sur l'écran /acces (frontend/components/site-access/SiteAccessGate.tsx), le champ de saisie du code d'accès du site est actuellement masqué (type="password", points noirs) : il doit afficher le texte saisi en clair. Le vocabulaire "mot de passe" employé sur cet écran (titre, libellé, texte d'aide, message d'erreur "Mot de passe incorrect.") doit être reformulé en "code d'accès", car ce n'est pas un mot de passe personnel mais un code partagé communiqué hors ligne par le club. La durée de validité de la session posée après validation du code (actuellement 7 jours) doit passer à 90 jours (3 mois). Hors périmètre : l'écran d'administration /admin/acces garde "mot de passe" ; le gate bénévoles n'est pas concerné ; le champ JSON de l'API et les identifiants techniques restent inchangés. Réfère l'issue GitHub #884."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Voir le code d'accès saisi en clair (Priority: P1)

Un visiteur qui reçoit le code d'accès du club (souvent recopié ou dicté) le saisit sur l'écran d'entrée du site et voit chaque caractère affiché en clair, pas masqué par des points.

**Why this priority**: C'est le changement qui prévient directement les erreurs de saisie (fautes de frappe invisibles sur un code partagé, pas un secret personnel à protéger visuellement) — la douleur la plus concrète et la plus fréquente.

**Independent Test**: Ouvrir l'écran `/acces`, saisir des caractères dans le champ de code d'accès, vérifier qu'ils restent visibles à l'écran (pas de points noirs), indépendamment des deux autres changements.

**Acceptance Scenarios**:

1. **Given** l'écran `/acces` affiché, **When** le visiteur saisit des caractères dans le champ de code d'accès, **Then** chaque caractère saisi reste visible en clair, à aucun moment masqué.
2. **Given** un champ de code d'accès déjà rempli, **When** le visiteur relit son contenu avant de valider, **Then** il peut vérifier visuellement l'exactitude de sa saisie sans avoir à la ressaisir.

---

### User Story 2 - Bénéficier d'une session valable 3 mois (Priority: P2)

Un visiteur qui a déjà validé le code d'accès n'a pas à le ressaisir à chaque visite pendant une période prolongée.

**Why this priority**: Réduit la friction récurrente (ressaisie hebdomadaire) pour l'ensemble des visiteurs déjà validés ; dépend d'une configuration serveur simple, sans impact sur l'écran de saisie.

**Independent Test**: Valider le code d'accès, puis constater que la session reste active sans nouvelle saisie jusqu'à 90 jours après la validation (vérifiable via la date d'expiration posée par le serveur au moment de la validation).

**Acceptance Scenarios**:

1. **Given** un visiteur qui vient de valider le code d'accès, **When** il revient sur le site avant l'expiration des 90 jours, **Then** il accède directement au contenu sans ressaisir le code.
2. **Given** un visiteur dont la session a dépassé 90 jours depuis sa validation, **When** il revient sur le site, **Then** l'écran de saisie du code d'accès lui est à nouveau présenté.

---

### User Story 3 - Comprendre qu'il s'agit d'un code d'accès partagé, pas d'un mot de passe personnel (Priority: P3)

Un visiteur qui lit les textes de l'écran `/acces` (titre, libellé, aide, message d'erreur) comprend qu'on lui demande un code communiqué par le club, pas un mot de passe personnel à choisir ou à retenir seul.

**Why this priority**: Clarifie le vocabulaire et réduit la confusion, mais n'a pas d'effet fonctionnel direct sur la capacité à se connecter — c'est un gain de compréhension, pas un déblocage.

**Independent Test**: Ouvrir l'écran `/acces` et déclencher une saisie incorrecte ; vérifier que tous les textes visibles (titre, libellé, aide, message d'erreur) emploient "code d'accès" et non "mot de passe".

**Acceptance Scenarios**:

1. **Given** l'écran `/acces` affiché, **When** le visiteur lit le titre, le libellé du champ et le texte d'aide, **Then** aucun de ces textes n'emploie le terme "mot de passe".
2. **Given** un visiteur qui saisit un code incorrect, **When** le message d'erreur s'affiche, **Then** ce message emploie "code d'accès" et non "mot de passe".

---

### Edge Cases

- Que se passe-t-il si la session d'un visiteur expire pendant qu'il navigue sur le site (au-delà de 90 jours) ? Il doit être redirigé vers l'écran de saisie du code d'accès, comme c'est déjà le cas aujourd'hui à 7 jours.
- Le message d'erreur affiché en cas de code incorrect doit rester compréhensible et cohérent avec le nouveau vocabulaire, sans changer son comportement (mêmes conditions de déclenchement qu'aujourd'hui).
- L'écran d'administration `/admin/acces` continue d'employer "mot de passe" : un visiteur qui verrait successivement les deux écrans (peu probable, l'admin est réservé) ne doit pas être une source d'incohérence bloquante — c'est un choix de périmètre assumé, pas un oubli.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le champ de saisie du code d'accès sur l'écran `/acces` DOIT afficher en clair chaque caractère saisi, sans le masquer.
- **FR-002**: Les textes visibles de l'écran `/acces` (titre, libellé du champ, texte d'aide, message d'erreur en cas de code incorrect) DOIVENT employer "code d'accès" et non "mot de passe".
- **FR-003**: Une session ouverte après validation du code d'accès DOIT rester valide 90 jours (3 mois) à compter de sa création, contre 7 jours actuellement.
- **FR-004**: L'écran d'administration `/admin/acces` NE DOIT PAS être modifié par cette évolution : il continue d'employer "mot de passe".
- **FR-005**: Le gate d'accès de la page bénévoles (écran `/benevoles`) NE DOIT PAS être affecté par cette évolution.
- **FR-006**: Le contrat de l'API publiée `/api/v1` (nom du champ JSON transportant le code d'accès) NE DOIT PAS être modifié par cette évolution.

### Key Entities *(include if feature involves data)*

- **Session de code d'accès** : session ouverte côté visiteur après validation du code d'accès partagé du site ; possède une date de création et une durée de validité au terme de laquelle elle expire et le visiteur doit ressaisir le code.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% des caractères saisis dans le champ de code d'accès restent visibles en clair pendant la saisie, vérifiable visuellement ou par test automatisé.
- **SC-002**: Aucun texte visible de l'écran `/acces` (titre, libellé, aide, message d'erreur) ne contient le terme "mot de passe" après déploiement.
- **SC-003**: Une session validée reste active sans nouvelle saisie du code pendant 90 jours, et expire au-delà — vérifiable par la date d'expiration posée au moment de la validation.
- **SC-004**: L'écran d'administration `/admin/acces` conserve à l'identique son vocabulaire "mot de passe" après déploiement (aucune régression de périmètre).

## Assumptions

- Les 90 jours se comptent à partir de la création de la session (même mécanique que les 7 jours actuels), pas un renouvellement glissant qui repousserait l'expiration à chaque visite.
- Le champ de code d'accès reste un champ texte simple affiché en clair de façon permanente, sans bouton "afficher/masquer" additionnel : l'affichage en clair n'est pas une option activable par le visiteur, c'est le comportement par défaut et unique.
- Les sessions déjà ouvertes au moment du déploiement suivent leur propre date d'expiration déjà posée (7 jours depuis leur création) ; seules les nouvelles sessions créées après déploiement bénéficient des 90 jours.
- Le comportement de déclenchement du message d'erreur (code incorrect, champ vide, limitation du nombre de tentatives) n'est pas modifié : seul le vocabulaire du message change.
