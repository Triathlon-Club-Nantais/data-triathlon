# Exporter mes données depuis Mon compte (#1674) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** un compte connecté télécharge depuis `/mon-compte` un JSON de ses données (droit d'accès et de portabilité, art. 15 et 20 RGPD), sans écrire au club.

**Architecture:** `GET /auth/me/export`, garde `current_user`, sans `require_site_access` (un droit RGPD ne dépend pas du code du site, patron #1673). Le service `account_export.build(db, user)` assemble le document à partir des relations du compte et de deux lectures de dépôt ; le routeur pose `Content-Disposition: attachment`. Côté front, un simple lien `download` vers la route, comme le CSV de carrière (#1375). Pas de migration.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest ; Next.js 16, Vitest + RTL.

## Contenu exporté

- `account` : adresse, nom affiché, création, dernière visite.
- `identities` : fournisseur, libellé, adresse, création. **Jamais** `subject` ni `secret_hash`.
- `athlete` : la fiche rattachée (nom, prénom, sexe, date de naissance, club), ou `null`.
- `athlete_claim` : la demande de rattachement en cours ou refusée, ou `null`.
- `result_claims` : les réclamations de résultat.
- `season_goals` : tous les objectifs, toutes saisons, sans progression calculée.
- `volunteer_actions` : les déclarations faites par le compte et celles qui créditent la fiche rattachée ; ni le nom de l'athlète crédité, ni l'auteur (donnée d'une autre personne), un booléen `for_my_athlete` à la place.
- `results` : les résultats portés par la fiche, en attente et refusés compris ; ni les équipiers d'un relais, ni `raw_data`.

## Fichiers

- Create `backend/app/schemas/account_export.py`, `backend/app/services/account_export.py`.
- Modify `backend/app/repositories/volunteer_action_repository.py` (`list_for_account`), `backend/app/api/v1/auth.py` (route).
- Test `backend/tests/test_api/test_my_export_api.py` : 401 anonyme ; pièce jointe JSON ; seules les données du compte connecté sortent (deux comptes peuplés) ; aucun secret.
- Modify `frontend/components/auth/AccountPage.tsx` (carte « Mes données »), test `AccountPage.test.tsx`.
- Modify `frontend/components/legal/content/confidentialite.tsx` (droit d'accès, `updatedAt`).

## Tâches

1. Test API rouge, puis schéma, dépôt, service, route : vert.
2. Test front rouge (lien `href=/api/v1/auth/me/export`, attribut `download`), puis carte : vert.
3. Politique de confidentialité.
