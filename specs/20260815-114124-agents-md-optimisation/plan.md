# Implementation Plan: Optimisation des fichiers AGENTS.md avec référence

**Branch**: `20260815-114124-agents-md-optimisation` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260815-114124-agents-md-optimisation/spec.md`

## Summary

Issue #335 (scope élargi via commentaires) : (1) split des `AGENTS.md` de
dossier mesurablement verbeux vers des fichiers de référence sous `docs/`,
patron déjà en place pour `backend/app/scrapers/AGENTS.md` ; (2) documenter la
convention d'assignation GitHub (issue → PR → reviewer) ; (3) préciser que les
titres d'issues suivent la règle anglaise du Principe I ; (4) vérifier la
règle sur les commentaires de code — déjà couverte par le Principe VI de la
constitution, donc **pas de duplication**. Aucun code exécutable : uniquement
des fichiers `.md`.

## Technical Context

**Language/Version**: N/A — feature purement documentaire (fichiers `.md`)

**Primary Dependencies**: N/A

**Storage**: N/A

**Testing**: N/A — pas de code exécutable ; vérification par lecture et
mesure de taille (`wc -l`), pas de suite de tests

**Target Platform**: Dépôt Git (agents IA + contributeurs humains)

**Project Type**: Documentation / configuration de dépôt

**Performance Goals**: Réduction mesurable du nombre de lignes chargées
automatiquement par le mécanisme `CLAUDE.md`→`@AGENTS.md` de dossier (cible
≥ 40 % sur les deux fichiers identifiés, cf. SC-001)

**Constraints**: Sobriété explicitement demandée par le porteur produit — pas
de nouvelle section longue, pas de réécriture générale, aucune information
perdue (déplacée, jamais supprimée)

**Scale/Scope**: 2 fichiers `AGENTS.md` de dossier à fragmenter
(`backend/app/api/`, `backend/app/services/auth/`), 4 nouveaux fichiers de
référence sous `docs/`, ~10-15 lignes ajoutées à `AGENTS.md` racine pour les
volets 2-3

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | La feature applique et clarifie ce principe (titres d'issues) ; tout le texte ajouté suit déjà la répartition français métier / English technique |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Aucun code applicatif touché — uniquement des fichiers `.md` |
| III | TDD sans réseau (non-négociable) | N/A | Aucun comportement exécutable introduit ; rien à tester par pytest. Vérification par lecture + `wc -l` |
| IV | Contrats API et CLI stables | N/A | Aucune route, schéma ou sortie CLI modifiée |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre applicatif introduit |
| VI | Simplicité / YAGNI | ✅ | Le split ne s'applique qu'aux 2 fichiers mesurés (pas de réécriture générale) ; le volet « commentaires de code » n'ajoute rien puisque déjà couvert par ce même principe — évite la duplication qu'il proscrit lui-même |

Aucune violation à justifier. Gate passée.

## Project Structure

### Documentation (this feature)

```text
specs/20260815-114124-agents-md-optimisation/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 : audit des fichiers candidats
├── quickstart.md        # Phase 1 : vérification manuelle du résultat
└── tasks.md             # Phase 2 (/speckit-tasks)
```

Pas de `data-model.md` (aucune entité de données — feature documentaire) ni de
`contracts/` (aucune interface externe exposée).

### Source Code (repository root)

Aucune arborescence de code n'est créée. Fichiers modifiés/créés :

```text
AGENTS.md                                    # + conventions (volets 2-3), inchangé sinon
backend/app/api/AGENTS.md                    # allégé, renvois vers docs/api/
backend/app/services/auth/AGENTS.md          # allégé, renvois vers docs/auth/
docs/api/courses-sources-fusion.md           # nouveau — epic #275 (#284-#287)
docs/api/admin-donnees.md                    # nouveau — #169 (endpoint), #117, #288
docs/api/feedback-stats.md                   # nouveau — #267, #272
docs/auth/liste-autorisation.md              # nouveau — #170
docs/auth/groupes.md                         # nouveau — #197
```

**Structure Decision** : documentation pure, aucune structure applicative
nouvelle. Les nouveaux fichiers suivent le patron déjà établi par
`docs/scrapers/<fournisseur>.md`.

## Complexity Tracking

*Aucune violation à justifier — section non applicable.*
