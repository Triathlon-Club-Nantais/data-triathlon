# Feature Specification: Suppression d'un compte par l'exploitant

**Feature Branch**: `epic/1312-member-accounts` (commits directs, revue sur la PR parapluie #1379)

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #1634. La suppression en libre service (#1326) est refusée en 409 quand une donnée à référence obligatoire cite le compte (journal d'administration, configuration de l'accès bénévoles, doublons ou cas d'identité écartés, validations de saison) ; la purge des 5 ans le saute. L'exploitant n'a aucun outil pour honorer une demande d'effacement.

## Clarifications

### Session 2026-10-19

- Q: Que devient la donnée qui cite le compte ? → A: elle reste, et passe au **compte système** des bénévoles, qui signe déjà le journal des suppressions : l'auteur devient « le club ». Rien du club n'est effacé.
- Q: Quel geste ? → A: une commande CLI d'exploitation, passe à blanc par défaut ; `--yes` applique. Pas d'écran : un effacement de ce type reste rare et se fait sur demande écrite.
- Q: Le dernier administrateur ? → A: toujours protégé, comme en libre service.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'exploitant efface un compte cité par le club (Priority: P1)

**Independent Test**: un compte auteur d'une validation de saison et de lignes de journal ; passe à blanc : le rapport compte les références par colonne, rien ne change ; `--yes` : les références passent au compte système, le compte est supprimé, une ligne `account.delete` (origine `operator`) est journalisée.

**Acceptance Scenarios**:

1. **Given** un compte cité par des données obligatoires, **When** l'exploitant lance la commande sans `--yes`, **Then** elle rend le nombre de références par table et colonne, sans rien modifier.
2. **Given** le même compte, **When** il relance avec `--yes`, **Then** les références passent au compte système, le compte et ce qu'il possède sont supprimés, le journal porte `account.delete` avec l'origine `operator` et les `oid` Entra.
3. **Given** le dernier administrateur, **When** la commande s'applique, **Then** refus, rien n'est modifié.
4. **Given** le compte système, ou un identifiant inconnu, **Then** refus avec un code d'erreur d'usage.

## Requirements *(mandatory)*

- **FR-001**: La commande MUST désigner un compte par son identifiant ou son adresse.
- **FR-002**: Sans `--yes`, elle MUST être sans effet et rendre le décompte des références obligatoires par table et colonne.
- **FR-003**: Avec `--yes`, elle MUST réattribuer les références obligatoires au compte système, puis supprimer le compte comme la suppression en libre service, dans une seule transaction.
- **FR-004**: Le dernier administrateur et le compte système MUST rester protégés.
- **FR-005**: La procédure MUST être documentée dans `infra/entra-external-id/AGENTS.md` et `backend/app/cli/AGENTS.md`.

## Success Criteria *(mandatory)*

- **SC-001**: Une demande d'effacement refusée en 409 s'honore en deux commandes (passe à blanc, application), sans SQL à la main.

## Assumptions

- La liste des références obligatoires est celle que lit déjà `user_repository.required_references` (schéma), sans inventaire tenu à la main.
