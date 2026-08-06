# Quickstart — valider les actions d'administration

**Feature** : `specs/20260806-180938-admin-crud-actions/`

Comment prouver que la feature marche, du test unitaire au geste réel dans le
navigateur. À dérouler dans l'ordre : chaque étape suppose la précédente verte.

## Prérequis

```bash
cd backend
uv sync
uv run alembic upgrade head          # doit inclure la révision « admin action log »
```

Un premier administrateur, si la base est neuve (#115) :

```bash
uv run python -m app.cli grant-role --email <votre-adresse> --role admin
```

## 1. Suite de tests — le filet obligatoire

```bash
cd backend
uv run pytest -m "not integration"        # tout doit être vert (Principe III)
uv run ruff check .
```

Ciblé sur la feature :

```bash
uv run pytest tests/test_api/test_admin_data_api.py \
              tests/test_services/test_admin_actions.py \
              tests/test_repositories/test_admin_action_log_repository.py -v
```

Ce que ces tests doivent démontrer, un par critère d'acceptation :

| Critère | Ce qui est vérifié |
| --- | --- |
| AC1 / FR-002 | après suppression, `participation_repository.count_for_course` = 0 **et** les lignes ont disparu de la base |
| AC2 / FR-005 | `PATCH` d'un coureur vers une identité déjà prise → `409`, et la fiche est **inchangée** en base |
| FR-021 | idem pour une épreuve |
| AC3 / FR-003 | `athlete_id` réécrit, et une entrée `participation.reassign` existe |
| AC4 / FR-012 | chaque geste réussi laisse exactement **une** entrée avec auteur, action, entité, horodatage |
| FR-015 | chaque geste **refusé** laisse **zéro** entrée et **zéro** modification |
| FR-022 | une fiche coureur qui perd son dernier résultat disparaît ; une fiche qui garde un résultat reste |
| FR-006 | rattachement vers un coureur déjà classé sur l'épreuve → `409` |
| FR-009 | chaque route rend `403` sans le pouvoir, et `401` sans session |
| FR-023 | après correction d'épreuve, les temps et rangs des résultats sont identiques |
| SC-007 / FR-026 | le compte annoncé par `deletion-impact` est **exactement** celui supprimé ensuite — les deux définitions ne peuvent pas diverger |
| FR-025 | `GET /athletes` et `GET /athletes/{id}` ne rendent **aucune** `birth_date` ; `GET /admin/athletes` la rend, et exige `athletes:read` |

Front :

```bash
cd frontend
npm test          # vitest — modales de confirmation, gating par pouvoir, messages 401/403
npm run build     # TS strict + RSC
```

## 2. Vérification manuelle de bout en bout

> **Comptez au passage** : chaque scénario doit tenir en moins de 5 interactions
> et moins de 30 secondes depuis l'arrivée sur le back-office (SC-002). C'est la
> seule mesure de ce critère — au-delà, il n'est pas tenu.

Deux terminaux :

```bash
cd backend  && uv run python scripts/dev_server.py     # publie son port
cd frontend && npm run dev                             # lit le port du worktree
```

Base de démonstration si besoin :

```bash
cd backend && uv run python scripts/reset_db.py
```

### Scénario A — supprimer une épreuve (User Story 1)

1. Connectez-vous, allez sur `/admin/courses`.
2. Notez le nombre de résultats d'une épreuve de démonstration.
3. « Supprimer » → la modale **nomme l'épreuve, le nombre de résultats et le
   nombre de fiches coureur** qui disparaîtront.
4. Relevez ces deux nombres, puis confirmez.

**Attendu** : l'épreuve disparaît de la liste et de `/courses` ; **exactement**
le nombre annoncé de fiches coureur a disparu de `/athletes` (SC-007) ; aucun
bouton « annuler ».

```bash
# la trace, côté base
cd backend && uv run python -c "
from app.core.database import SessionLocal
from app.models.admin_action_log import AdminActionLog
with SessionLocal() as db:
    for e in db.query(AdminActionLog).order_by(AdminActionLog.id.desc()).limit(5):
        print(e.created_at, e.user_id, e.action, e.entity_type, e.entity_id, e.payload)
"
```

### Scénario B — rattacher un résultat (User Story 2)

1. Sur une épreuve, ouvrez un résultat et choisissez « Rattacher à un autre
   coureur ».
2. Cherchez le coureur cible : chaque proposition affiche **date de naissance,
   club et nombre de résultats** — de quoi départager deux homonymes.
3. Sélectionnez-le, confirmez.

**Attendu** : le résultat figure dans l'historique de la cible, plus dans celui
de la source ; si la source n'avait que lui, sa fiche a disparu ; une entrée
`participation.reassign` est au journal.

**Refus à vérifier** : viser un coureur déjà classé sur cette épreuve → message
français, rien ne bouge.

### Scénario C — corriger un coureur (User Story 3)

1. Corrigez le nom d'un coureur, validez → le nouveau nom s'affiche partout, son
   historique est intact.
2. Recommencez en visant l'identité **exacte** d'un autre coureur → refus
   nommant la fiche en conflit, rien ne bouge.

### Scénario D — corriger une épreuve (User Story 4)

1. Renommez une épreuve → le nouveau libellé s'affiche, ses résultats lui
   restent tous rattachés, leurs temps et rangs sont inchangés.
2. Visez l'identité exacte d'une autre épreuve (mêmes nom, date, type, relais)
   → refus nommant l'épreuve en conflit.

### Scénario E — les droits (FR-009, FR-011)

1. Créez un rôle sans aucun des cinq pouvoirs, attribuez-le à un compte de
   test (`/admin/roles`).
2. Connecté avec ce compte : `/admin/courses` **ne propose aucun bouton
   d'action**.
3. Sollicitez la route directement :

```bash
curl -i -X DELETE "http://localhost:<port>/api/v1/admin/courses/1" -b "<cookie de session>"
# attendu : 403 {"detail":"Vous n'avez pas les droits nécessaires pour cette action."}
curl -i -X DELETE "http://localhost:<port>/api/v1/admin/courses/1"
# attendu : 401
```

## 3. Ce qui doit rester intact

Non-régressions à constater avant de considérer la branche finie :

- `POST /api/v1/admin/pending-providers` répond toujours **sans session** — le
  signalement du site public ne doit jamais tomber derrière une garde de préfixe.
- `GET /api/v1/courses`, `/courses/{id}`, `/courses/{id}/summary`,
  `/participations` : contrats inchangés (Principe IV).
- `uv run python -m app.cli rescrape-db --limit 1 --json | jq .orphans_removed`
  renvoie toujours un entier — la signature de `delete_orphans` n'a pas bougé
  pour son appelant historique.
- `curl "http://localhost:<port>/api/v1/athletes?name=dup" | jq '.[0]'` ne
  contient **aucune** `birth_date` — la lecture publique n'a pas été enrichie
  (FR-025).

## Références

- Contrat des routes : [`contracts/admin-data-api.md`](contracts/admin-data-api.md)
- Modèle et invariants : [`data-model.md`](data-model.md)
- Décisions techniques : [`research.md`](research.md)
