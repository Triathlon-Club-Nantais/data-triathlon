# Data Model — Skill « onboard »

Trois entités logiques. Une seule est persistée sur disque (`state.json`).

## Entité 1 — Profil contributeur (en mémoire de session)

Ce que le skill retient pour adapter le parcours. Non persisté directement —
matérialisé dans `answers` du `state.json`.

**Champs** :

| Champ | Type | Valeurs autorisées | Origine |
|-------|------|-------------------|---------|
| `profile` | enum | `fullstack` \| `backend` \| `frontend` | Q1 posée au démarrage |
| `experience_level` | enum | `nouveau` \| `retour` | Q2 |
| `db_choice` | enum | `sqlite` \| `supabase` | Q3 (uniquement si `.env` absent) |
| `verbosity` | enum | `courte` \| `complete` | Q4 |
| `skip_ia_tooling` | bool | `true` \| `false` | Q5 |

**Règles** :
- Les 5 questions sont posées **au maximum une fois** par invocation ;
  les réponses sont conservées entre invocations via `state.answers`.
- Si `experience_level=retour` et `state.step_install=done`, alors Q3 (DB)
  n'est **pas** re-posée.

## Entité 2 — État de progression (persisté)

Fichier : `.claude/skills/onboard/state.json` (git-ignoré).

**Schéma** : voir `contracts/state-schema.json`.

**Structure** :

```json
{
  "schema_version": 1,
  "last_updated": "2026-07-27T10:15:00Z",
  "answers": {
    "profile": "fullstack",
    "experience_level": "nouveau",
    "db_choice": "sqlite",
    "verbosity": "complete",
    "skip_ia_tooling": false
  },
  "steps": {
    "prerequisites":  "done",
    "install":        "done",
    "db":             "done",
    "tests":          "done",
    "dev":            "done",
    "tour":           "pending",
    "ia_tooling":     "pending",
    "first_feature":  "pending"
  }
}
```

**Statuts d'étape** :

| Statut | Signification |
|--------|---------------|
| `pending` | Pas encore commencée. |
| `done` | Terminée avec succès, artefacts vérifiés (venv, DB, etc.). |
| `skipped` | Sautée sur choix du contributeur ou parce que déjà OK. |
| `failed` | A échoué à la dernière tentative. Un `failed` **bloque** la progression : le skill le signale et attend une action. |

**Transitions d'état** :

```text
                     ┌─────────────┐
                     │   pending   │
                     └──────┬──────┘
                            │  (le skill exécute l'étape)
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌─────────┐  ┌────────────┐  ┌────────┐
        │ skipped │  │  failed    │  │  done  │
        └─────────┘  └─────┬──────┘  └────────┘
                           │  (retry manuel)
                           ▼
                        pending
```

**Règles** :
- `last_updated` est **toujours** mis à jour à chaque écriture.
- Si `schema_version` du fichier ≠ version courante du skill, le skill
  invalide le state et propose de redémarrer.
- Si le fichier existe mais est mal formé (JSON invalide, clé
  manquante), même traitement.

## Entité 3 — État d'installation (calculé)

Non stocké. Recalculé à chaque invocation par une série de sondes shell.

**Champs** :

| Champ | Sonde | Interprétation |
|-------|-------|----------------|
| `env_present` | `[ -f backend/.env ]` | .env créé (par le skill ou manuellement) |
| `venv_present` | `[ -d backend/.venv ]` | `uv sync` a été exécuté |
| `node_modules_present` | `[ -d frontend/node_modules ]` | `npm install` a été exécuté |
| `db_populated` | `[ -f backend/triathlon.db ] && [ $(stat -c%s backend/triathlon.db) -gt 100000 ]` | Seed a produit une DB > 100 Ko (empirique : la DB seed pèse ~5 Mo) |
| `backend_up` | `curl -sSo /dev/null -w '%{http_code}' http://localhost:8001/docs` == `200` | Backend écoute |
| `frontend_up` | `curl -sSo /dev/null -w '%{http_code}' http://localhost:3000` == `200/307` | Front écoute |
| `gh_installed` | `command -v gh` code 0 | `gh` disponible |
| `gh_authenticated` | `gh auth status` code 0 | `gh` authentifié |

**Règles** :
- La détection est **factuelle** : si elle contredit un statut `done` du
  state, la détection l'emporte et l'étape est rejouée.
- Les sondes qui font du réseau (`curl :8001`, `gh auth status`) ont un
  timeout court (2s) pour ne pas bloquer.

## Invariants inter-entités

- Si `state.steps.install = "done"` **et** `venv_present = false`, alors
  le skill **rejoue** l'étape install (ne fait pas confiance aveuglément
  au state).
- Si `answers.db_choice = "supabase"` **et** `env_present = false` **et**
  la valeur `.env` construite est vide, l'étape échoue explicitement
  plutôt que d'écrire un `.env` vide.
- `answers.skip_ia_tooling = true` transitionne `steps.ia_tooling` et
  `steps.first_feature` directement à `skipped`.
