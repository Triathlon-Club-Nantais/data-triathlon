# Feature Specification: Relevé et rappel des effacements Entra

**Feature Branch**: `epic/1312-member-accounts` (commits directs, revue sur #1379)

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #1635. Après la suppression d'un compte (#1326, #1634), l'utilisateur Entra External ID reste dans l'annuaire : la suppression automatique est payante. La procédure est manuelle (`infra/entra-external-id/AGENTS.md`) : relever les `oid` du journal `account.delete`, puis les supprimer par `az rest`. Rien ne la rappelle.

## Clarifications

### Session 2026-10-19

- Q: Quel rappel, sans coût ? → A: la reprise hebdomadaire planifiée (`batch.yml`, lundi) relève les suppressions de la semaine ; s'il y a des identifiants Entra à effacer, elle ouvre ou complète une issue `ops` « Entra directory deletions to finish ».
- Q: Le dépôt est public : quoi dans l'issue ? → A: le **nombre** seul et la commande à lancer en local, jamais les `oid` (pseudonymes, mais données personnelles).
- Q: Quelle base ? → A: la production, comme la purge planifiée qu'elle suit ; la commande ne compare jamais l'annuaire à une base.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'exploitant sait quoi effacer et quand (Priority: P1)

**Independent Test**: deux suppressions journalisées, l'une avec deux `oid`, l'autre sans ; `entra-deletions --since` liste les deux `oid` avec la commande `az rest` de chacun, et ignore la suppression sans `oid` ou plus ancienne que la date.

**Acceptance Scenarios**:

1. **Given** des suppressions journalisées depuis une date, **When** l'exploitant lance la commande, **Then** elle rend chaque `oid` avec sa commande `az rest --method delete`, et le total.
2. **Given** aucune suppression à finir, **Then** elle le dit et rend 0.
3. **Given** la reprise du lundi, **When** la semaine compte des `oid`, **Then** une issue `ops` est ouverte ou complétée avec leur nombre et la commande à lancer, sans les `oid`.

## Requirements *(mandatory)*

- **FR-001**: Une commande CLI en lecture seule MUST lister les `oid` Entra des lignes `account.delete` depuis une date (défaut : 35 jours), avec la commande `az rest` de chacun et le total ; `--count` rend le seul total.
- **FR-002**: La reprise planifiée MUST l'exécuter sur les 7 derniers jours et ouvrir ou compléter une issue `ops` quand le total est positif, sans y écrire d'`oid`.
- **FR-003**: La procédure MUST être mise à jour dans `infra/entra-external-id/AGENTS.md`.

## Success Criteria *(mandatory)*

- **SC-001**: Aucune suppression Entra n'attend plus d'une semaine sans rappel.

## Assumptions

- Le journal garde les `oid` 12 mois (`payload.entra_oids`), au delà de la fenêtre utile.
