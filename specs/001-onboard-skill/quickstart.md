# Quickstart — Validation manuelle du skill `/onboard`

Ce document remplace la suite pytest classique (voir Complexity Tracking du
`plan.md`). Il documente trois scénarios reproductibles que le mainteneur
DOIT rejouer avant de merger la PR de livraison du skill.

Chaque scénario liste (a) l'état initial à préparer, (b) les réponses
attendues aux 5 questions, (c) les invariants à vérifier à la fin.

---

## Scénario 1 — Premier onboarding « from scratch » (User Story 1, MVP)

**Préparer l'état initial** :

```bash
cd /path/to/data-triathlon
rm -f backend/.env backend/triathlon.db
rm -rf backend/.venv frontend/node_modules
rm -f .claude/skills/onboard/state.json
# Vérifier qu'on est sur une branche de travail, pas main
git status
```

**Invocation** : `/onboard` dans Claude Code, session ouverte sur la racine
du dépôt.

**Réponses attendues aux 5 questions** :

| # | Question | Réponse |
|---|----------|---------|
| Q1 | Sur quelle couche vas-tu contribuer ? | `fullstack` |
| Q2 | Nouveau contributeur ou retour ? | `nouveau` |
| Q3 | SQLite (local) ou Supabase ? | `sqlite` |
| Q4 | Version courte ou complète ? | `complete` |
| Q5 | Sauter la présentation Speckit/Superpowers ? | `non` |

**Invariants à vérifier à la fin** :

1. `backend/.env` existe et contient `DATABASE_URL=sqlite:///./triathlon.db`.
2. `backend/.venv/` existe (créé par `uv sync`).
3. `backend/triathlon.db` fait > 100 Ko.
4. `frontend/node_modules/` existe.
5. `.claude/skills/onboard/state.json` existe et valide contre
   `contracts/state-schema.json` :
   - `steps.prerequisites = "done"`, `install = "done"`, `db = "done"`,
     `tests = "done"`, `dev = "done"`, `tour = "done"`,
     `ia_tooling = "done"`, `first_feature = "done"` (ou `skipped`).
6. `curl -s http://localhost:8001/docs` → HTTP 200.
7. `curl -s http://localhost:3000` → HTTP 200/307.
8. Le contributeur (le mainteneur qui rejoue) peut, sans relire la doc,
   citer 3 des 6 principes de la constitution et la différence vibe /
   feature complète.
9. Chrono : ≤ 15 minutes (SC-001).

---

## Scénario 2 — Retour après pause (User Story 2)

**Préparer l'état initial** : partir de la fin du Scénario 1
(env installé, tests verts). Optionnellement, tuer les serveurs de dev.

**Invocation** : `/onboard`.

**Réponses attendues** :

| # | Question | Réponse |
|---|----------|---------|
| Q1 | Couche ? | `fullstack` (ou selon profil) |
| Q2 | Nouveau ou retour ? | `retour` |
| Q3 | *(non posée, .env préexistant)* | — |
| Q4 | Verbosité ? | `courte` |
| Q5 | Sauter IA tooling ? | `non` |

**Invariants** :

1. Le skill DOIT afficher la valeur `DATABASE_URL` détectée dans `.env`
   sans jamais proposer de l'écraser (FR-005 clarifié).
2. `uv sync` **n'est pas** relancé si `.venv/` est déjà présent et que
   `pyproject.toml` n'a pas bougé (le skill peut hasher pour vérifier).
3. `task test` est **rejoué** rapidement (~5s attendu) — c'est la seule
   étape non-skippable, elle garantit qu'aucune régression locale n'est
   passée.
4. Chrono : ≤ 3 minutes (SC-005).

---

## Scénario 3 — Contributeur mono-couche : frontend only (User Story 3)

**Préparer l'état initial** : identique au Scénario 1 (état vierge).

**Invocation** : `/onboard`.

**Réponses attendues** :

| # | Question | Réponse |
|---|----------|---------|
| Q1 | Couche ? | `frontend` |
| Q2 | Nouveau ou retour ? | `nouveau` |
| Q3 | DB ? | `sqlite` |
| Q4 | Verbosité ? | `complete` |
| Q5 | Sauter IA tooling ? | `non` |

**Invariants** :

1. Le tour de code **ne** mentionne **pas** les scrapers, ni
   `app/services/import_service.py`, ni `app/scrapers/klikego.py`.
2. Le tour de code couvre : `frontend/app/` (App Router), `frontend/lib/`
   (`api/`, `sse.ts`, `types.ts`), le contrat API `/api/v1` (côté
   consommation seulement).
3. La suggestion `good first issue` DOIT être filtrée sur `label:frontend`
   si ce label existe sur les issues remontées.

---

## Cas de bord à vérifier

### CB1 — Prérequis manquant

**Préparer** : renommer temporairement `uv` (`sudo mv /usr/local/bin/uv
/usr/local/bin/uv.bak`) puis lancer `/onboard`.

**Attendu** : le skill détecte l'absence, affiche la commande d'install
officielle (`curl -LsSf https://astral.sh/uv/install.sh | sh`), et attend
que le contributeur ait installé. Après réinstallation, il rescanne.

**Restaurer** : `sudo mv /usr/local/bin/uv.bak /usr/local/bin/uv`.

### CB2 — Test qui échoue

**Préparer** : injecter volontairement un test rouge, par exemple modifier
`backend/tests/test_core/test_config.py` pour qu'une assertion échoue.

**Attendu** : `task test` sort en échec, le skill **s'arrête** et affiche
la sortie d'erreur. `steps.tests = "failed"` dans le `state.json`. Le
skill **ne lance pas** `task dev` (FR-007).

**Restaurer** : `git checkout backend/tests/`.

### CB3 — `gh` absent

**Préparer** : renommer `gh` (`sudo mv /usr/local/bin/gh /usr/local/bin/gh.bak`).

**Attendu** : à l'étape « première feature », le skill affiche la commande
d'install de `gh` et propose de skipper. `steps.first_feature = "skipped"`.

**Restaurer** : `sudo mv /usr/local/bin/gh.bak /usr/local/bin/gh`.

### CB4 — `.env` préexistant

**Préparer** : après Scénario 1, sans supprimer `.env`, relancer
`/onboard`.

**Attendu** : le skill affiche la valeur `DATABASE_URL` détectée et
**passe à l'étape suivante** sans proposer d'écrasement (FR-005 clarifié).

---

## Signature de validation

Une fois les 3 scénarios + 4 cas de bord validés, le mainteneur DOIT
signer la PR de livraison en indiquant explicitement dans la description :

```
Quickstart validé le YYYY-MM-DD :
- [x] Scénario 1 (fresh) : X min
- [x] Scénario 2 (retour) : Y min
- [x] Scénario 3 (frontend only)
- [x] CB1 uv absent
- [x] CB2 test rouge
- [x] CB3 gh absent
- [x] CB4 .env préexistant
```
