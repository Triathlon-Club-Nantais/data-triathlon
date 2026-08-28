---
name: product-owner
description: Use when the user wants to groom, refine, triage, or prioritize the open GitHub issue backlog, wants issues clustered into epics or linked as GitHub sub-issues, or wants the "Data TCN" project board's Status/Priority fields updated.
---

# Product Owner

## Overview

Balaie tout le backlog GitHub ouvert, raffine les issues qui n'atteignent
pas la Definition of Ready, les regroupe en epics, pose une priorité sur le
board, et applique/documente le workflow git des epics multi-issues.
Fonctionne en dry-run : rien n'est écrit sur GitHub avant validation
explicite du plan par l'utilisateur.

**REQUIRED BACKGROUND:** `docs/gestion-de-projet.md` — Definition of
Ready, modèle d'epic, échelle de priorité, rôle des milestones, workflow
git. Cette skill applique cette convention, elle ne la redéfinit pas.

**REQUIRED REFERENCE:** `reference/graphql.md` — commandes `gh api
graphql`/`gh project` exactes (liaison sub-issue, champs du board, IDs).

## Quand l'utiliser

- "Raffine le backlog", "fais le tri dans les issues", "priorise le
  backlog".
- "Regroupe ces issues en epic", "crée une epic pour X".
- Avant une réunion/release, pour remettre le board à jour.

## Déroulé

1. **Collecter** : `gh issue list --state open --limit 500` (backlog
   complet) + `gh project item-list 1 --owner Triathlon-Club-Nantais --limit
   500` pour les items du board — la limite par défaut est 30 pour les deux
   commandes et elles tronquent silencieusement (le backlog et le board
   comptent plusieurs centaines d'entrées). Résoudre une fois les IDs de
   champs (`reference/graphql.md`), les garder en mémoire pour le reste de
   l'invocation.
2. **Analyser** chaque issue contre la Definition of Ready
   (`docs/gestion-de-projet.md`). Une issue qui la satisfait déjà sort de
   la liste de travail. Pour les autres, dispatcher un agent
   `Explore`/`general-purpose` si le raffinement demande de lire du code,
   et proposer : titre, corps structuré, labels, priorité, scission (si
   plusieurs tâches sont bundlées), rattachement à une epic.
3. **Regrouper en epics** : rattacher en priorité aux epics `label:epic`
   déjà existantes ; n'en proposer une nouvelle que si aucune epic
   existante ne correspond à l'objectif partagé par ≥2 issues. Le corps
   d'une epic proposée ne duplique pas le workflow git — il y renvoie :
   `Workflow : voir docs/gestion-de-projet.md#workflow-git-dune-epic-multi-issues`.
4. **Présenter le plan en chat**, groupé par epic puis « sans epic »,
   chaque ligne = état actuel → changement proposé. Une issue Ready/Done
   qui semble former une release cohérente est signalée séparément
   ("ces N issues ressemblent à v0.7.0, je crée le milestone ?") — jamais
   appliqué sans confirmation dédiée à ce point précis.
5. **Attendre l'approbation explicite du lot** (ajustable en langage
   naturel : "saute la #123", "fusionne avec l'epic X") avant d'écrire quoi
   que ce soit sur GitHub.
6. **Appliquer**, dans l'ordre : créer les epics → scinder les issues
   bundlées → éditer titre/corps/labels/priorité → lier les sub-issues
   (`reference/graphql.md`) → poser les champs du board → passer `Ready`
   si la Definition of Ready est atteinte → pour toute issue qui reste en
   `Backlog` faute d'information, poster le commentaire listant ce qui
   manque (Definition of Ready, `docs/gestion-de-projet.md`) — ce
   commentaire est écrit sur GitHub au même titre que les autres
   changements du lot, pas seulement décrit dans le rapport en chat. Ne
   jamais créer de milestone sans confirmation dédiée.
7. **Rapporter** : ce qui a été appliqué, ce qui a échoué (le cas échéant,
   sans retry automatique — voir `reference/graphql.md`), ce qui reste en
   `Backlog` faute d'information.

## Ré-invocation

Une issue déjà conforme à la Definition of Ready n'apparaît plus dans le
plan suivant — pas de ré-écriture inutile. Le statut d'une epic est
recalculé à chaque passe, jamais incrémenté.

## Erreurs courantes

| Situation | À faire |
| --- | --- |
| Une seule sous-issue prête, l'epic n'a pas encore de branche d'intégration | Le rappeler dans le plan, ne pas créer la branche avant qu'au moins une sous-issue soit prête à démarrer. |
| Une issue déjà bien écrite (Definition of Ready presque atteinte) | Ne proposer que ce qui manque réellement (souvent : juste labels + priorité) — ne pas réécrire un corps déjà conforme. |
| Board et labels en désaccord (ex. `Priority` posé sur le board mais pas de label de domaine) | Traiter chaque critère de la Definition of Ready indépendamment — un critère manquant suffit à garder l'issue hors de `Ready`. |
