# Quickstart — valider les actions d'administration sur la page d'un coureur (#439)

Comment vérifier que la feature marche, de bout en bout. Chaque scénario nomme
son critère de succès de la spec.

## Prérequis

```bash
# Backend — depuis backend/ (aucun venv à activer, uv s'en charge)
uv sync
uv run alembic upgrade head          # applique la migration club_locked
uv run python scripts/reset_db.py    # base SQLite vierge + jeu de démonstration

# Frontend — depuis frontend/
npm install
```

Le backend prend le premier port libre à partir de 8001 et le publie ; le
frontend le lit. Rien à configurer entre les deux
(`docs/dev-multi-worktree.md`).

```bash
uv run python scripts/dev_server.py   # backend + /docs
npm run dev                           # frontend
```

Pour éprouver la visibilité pouvoir par pouvoir, il faut des rôles ne portant
qu'**un** des quatre pouvoirs. Les composer depuis l'écran d'administration des
rôles, ou par l'API (`POST /api/v1/admin/roles`) avec un seul code dans
`permissions` : `athletes:write`, `participations:delete`,
`participations:reassign`, `athletes:read`.

## Suites automatisées

```bash
# Backend — unitaires, sans réseau (le défaut CI)
cd backend
uv run pytest -m "not integration"
uv run ruff check .

# Les fichiers de cette feature, seuls
uv run pytest tests/test_repositories/test_athlete_repository.py \
              tests/test_repositories/test_participation_repository.py \
              tests/test_services/test_admin_actions.py \
              tests/test_services/test_import_service.py \
              tests/test_api/test_admin_data_api.py \
              tests/test_api/test_participations_api.py \
              tests/test_migrations.py

# Frontend
cd frontend
npm test
npm run lint
npm run build          # strict TS + RSC — la page doit rester rendable côté serveur
```

## Scénario 1 — Corriger l'identité sans quitter la page (US1, SC-001, SC-002)

1. Se connecter avec un rôle portant `athletes:write` **et** `athletes:read`.
2. Ouvrir `/athletes/<id>` d'un coureur mal orthographié.
3. **Attendu** : un accès aux corrections est visible dans l'en-tête.
4. L'ouvrir, corriger le nom, enregistrer.
5. **Attendu** : la modale se ferme, un toast de réussite s'affiche, **le nom en
   tête de page est le nouveau** — sans rechargement manuel.
6. Chercher le coureur dans la recherche publique.
   **Attendu** : le nouveau nom y apparaît.

**Mesure SC-001** : zéro navigation intermédiaire (contre trois auparavant : page
→ back-office → recherche → retour).

**Mesure SC-002** : compter les interactions des étapes 3 à 4, confirmation non
comptée. **Attendu : 2 au plus** — ouvrir l'accès, déclencher le geste. Refaire le
compte pour les trois autres actions (scénarios 4, 6 et 8) : chacune doit tenir
dans la même borne.

## Scénario 2 — Le conflit d'identité ne casse rien (US1-AC3, FR-010)

1. Relever l'identité complète d'un coureur B (nom, prénom, date de naissance).
2. Sur la fiche d'un coureur A, saisir exactement cette identité, enregistrer.
3. **Attendu** : la modale **reste ouverte**, le message nomme la fiche en
   conflit (« Un coureur porte déjà cette identité (fiche #N). »), **la saisie
   est conservée**.
4. Recharger la fiche de A.
   **Attendu** : rien n'a changé.
5. Vérifier le journal :
   ```bash
   sqlite3 backend/triathlon.db \
     "SELECT action, entity_id FROM admin_action_log ORDER BY id DESC LIMIT 3;"
   ```
   **Attendu** : aucune entrée pour ce geste refusé (SC-005).

## Scénario 3 — La date de naissance reste fermée (US1-AC4, D7)

1. Se connecter avec un rôle portant `athletes:write` **sans** `athletes:read`.
2. Ouvrir les corrections sur un coureur **dont la date de naissance est
   renseignée**.
3. **Attendu** : aucun champ de date de naissance dans le formulaire.
4. Corriger le nom, enregistrer.
5. Se reconnecter avec `athletes:read` et rouvrir la fiche.
   **Attendu** : la date de naissance est **intacte** — l'enregistrement ne l'a
   pas effacée.

## Scénario 4 — Supprimer un résultat (US2, SC-006, SC-007)

**Moitié A — un résultat validé : les indicateurs bougent**

1. Se connecter avec un rôle portant `participations:delete`.
2. Sur la fiche d'un coureur ayant plusieurs résultats **validés**, relever le
   nombre d'épreuves affiché par l'indicateur.
3. **Attendu** : chaque ligne du tableau porte une action de suppression.
4. La déclencher sur une ligne **validée**.
   **Attendu** : une confirmation nomme **l'épreuve** et dit l'irréversibilité ;
   rien n'est supprimé tant qu'on n'a pas confirmé (SC-006).
5. Annuler.
   **Attendu** : le résultat est toujours là.
6. Rouvrir, confirmer.
   **Attendu** : la ligne disparaît, **l'indicateur d'épreuves a décrémenté**, et
   les autres indicateurs (meilleure place, meilleur ratio, top 10, format
   favori) sont recalculés — sans rechargement manuel (SC-007).
7. Vérifier le journal :
   ```bash
   sqlite3 backend/triathlon.db \
     "SELECT action, entity_type, entity_id, payload FROM admin_action_log
      WHERE action = 'participation.delete' ORDER BY id DESC LIMIT 1;"
   ```
   **Attendu** : une entrée avec son auteur, et un `payload` où l'on **relit** ce
   qui a disparu — coureur, épreuve, place, temps (SC-005).

**Moitié B — une saisie en attente : aucun indicateur ne bouge (US2-AC6)**

1. Sur la fiche d'un coureur portant une ligne **en attente de validation**,
   relever les **cinq** indicateurs.
2. Supprimer cette ligne, confirmer.
3. **Attendu** : la ligne disparaît, un toast de réussite s'affiche, et **les cinq
   indicateurs sont inchangés** — ils ne portent que sur les résultats validés.
   Ce n'est pas un échec : c'est la disparition de la ligne qui atteste du geste.
4. **Attendu** : le journal porte bien une entrée `participation.delete`, comme
   pour un résultat validé.

## Scénario 5 — Le dernier résultat ne fait pas disparaître le coureur (US2-AC4, FR-012)

1. Sur un coureur n'ayant **qu'un** résultat, le supprimer.
2. **Attendu** : la fiche reste **accessible**, annonce l'absence de résultat, et
   le coureur n'est pas supprimé.
3. Vérifier :
   ```bash
   sqlite3 backend/triathlon.db "SELECT id, nom FROM athletes WHERE id = <id>;"
   ```
   **Attendu** : la ligne existe toujours.

## Scénario 6 — Changer le club, sans toucher l'historique (US3, FR-013)

1. Se connecter avec `athletes:write`.
2. Relever le club porté par un des **résultats** du coureur :
   ```bash
   sqlite3 backend/triathlon.db \
     "SELECT id, club FROM participations WHERE athlete_id = <id>;"
   ```
3. Corriger le club actuel vers le libellé exact du TCN
   (voir la liste blanche de `backend/app/core/club.py`), enregistrer.
4. **Attendu** : la page affiche le nouveau club ; le coureur apparaît dans la
   liste des coureurs du club.
5. Rejouer la requête de l'étape 2.
   **Attendu** : **les clubs des résultats sont inchangés** — l'historique
   conserve le club de l'époque.
6. Vider le champ club, enregistrer.
   **Attendu** : le coureur est enregistré **sans club actuel** (`NULL`), et non
   avec une chaîne vide :
   ```bash
   sqlite3 backend/triathlon.db \
     "SELECT club, club IS NULL, club_locked FROM athletes WHERE id = <id>;"
   ```

## Scénario 7 — Le club corrigé à la main survit à l'import (US3-AC4/AC5, SC-008)

C'est le scénario porteur de la seule addition de schéma. Il se joue en deux
moitiés : le club figé **résiste**, le club jamais corrigé **suit**.

**Moitié A — le club figé résiste**

1. Choisir un coureur figurant dans une épreuve déjà importée, avec un libellé de
   club donné par le chronométreur.
2. Corriger son club à la main vers une autre valeur.
   ```bash
   sqlite3 backend/triathlon.db "SELECT club, club_locked FROM athletes WHERE id = <id>;"
   ```
   **Attendu** : la nouvelle valeur, et `club_locked = 1`.
3. Réimporter l'épreuve (rescrape depuis la page de l'épreuve, ou
   `uv run python -m app.cli rescrape-db`).
4. Rejouer la requête.
   **Attendu** : **la correction tient** — `club` inchangé, zéro réécriture
   (SC-008).

**Moitié B — le club jamais corrigé suit l'import**

1. Choisir un autre coureur de la **même** épreuve, jamais corrigé
   (`club_locked = 0`).
2. Réimporter.
3. **Attendu** : son club actuel suit le libellé de l'import, comme avant la
   feature. La feature ne change **rien** pour lui.

## Scénario 8 — Rattacher un résultat au bon coureur (US4)

1. Se connecter avec `participations:reassign` **et** `athletes:read`.
2. Sur la fiche du coureur A, déclencher le rattachement d'un résultat.
3. **Attendu** : le sélecteur affiche nom, prénom **et date de naissance** — de
   quoi départager deux homonymes.
4. Choisir le coureur B, valider.
5. **Attendu** : le résultat quitte la fiche de A, apparaît sur celle de B, et le
   journal porte une entrée `participation.reassign` avec son auteur.
6. Rejouer le geste en désignant le coureur qui porte **déjà** le résultat.
   **Attendu** : l'écran le dit, **rien n'est écrit ni journalisé** (US4-AC2,
   FR-014).

## Scénario 9 — Ne voir que ce que l'on peut faire (US5, SC-003)

Charger la **même** fiche dans quatre états et compter les actions offertes.

| État de session | Actions attendues |
| --- | --- |
| Déconnecté | **aucune** ; page identique à ce qu'elle était avant la feature |
| Connecté, aucun des 4 pouvoirs | **aucune** |
| `participations:delete` seul | la suppression sur chaque ligne, **et rien d'autre** |
| `athletes:write` seul | les corrections dans l'en-tête, **et rien d'autre** |
| `participations:reassign` **sans** `athletes:read` | **aucune** — le sélecteur serait inutilisable (D6) |
| Les quatre pouvoirs | les quatre actions |

**Mesure SC-003** : le nombre d'actions offertes est **exactement** celui des
pouvoirs qui **suffisent** à un geste, vérifié pour les quatre pouvoirs pris un
par un. Un pouvoir couplé compte pour zéro tant que son binôme manque.

**Contrôle du back-office, dans le même état de session (FR-020, US4-AC3)** : en
restant connecté avec `participations:reassign` **sans** `athletes:read`, ouvrir
une épreuve dans le back-office et son dialogue de participations.
**Attendu** : **aucune** action de rattachement n'y est offerte non plus. Avant
cette branche, elle l'était — et se terminait en `403` dès la première frappe
dans le sélecteur.

## Scénario 10 — Le masquage n'est pas une protection (US5-AC5, FR-009)

Contourner l'interface et appeler l'API directement, sans le pouvoir :

```bash
curl -i -X DELETE http://localhost:<port>/api/v1/participations/<id>
# Attendu : 401 ou 403 — et rien n'est supprimé

curl -i -X PATCH http://localhost:<port>/api/v1/admin/athletes/<id> \
     -H 'Content-Type: application/json' -d '{"club": "Peu importe"}'
# Attendu : 401 ou 403 — et ni club, ni club_locked ne bougent
```

Puis vérifier que le journal n'a **rien** enregistré pour ces tentatives
(SC-005).

## Scénario 11 — Le visiteur anonyme ne paie rien de plus (SC-004)

1. Ouvrir `/athletes/<id>` en navigation privée, onglet réseau ouvert.
2. **Attendu** : **aucun** appel à `/api/v1/auth/session` — le cookie témoin
   `tcn_logged_in` est absent, `useSession()` court-circuite la requête.
3. Comparer le HTML servi à celui d'avant la branche : même volume de données,
   même mode de rendu.
   ```bash
   npm run build   # la page /athletes/[id] doit conserver son mode de rendu
   ```
   **Attendu** : la page n'a pas basculé en rendu dynamique.

## Scénario 12 — La ressource a disparu entre-temps (FR-016, US2-AC5)

1. Ouvrir la même fiche dans deux navigateurs, tous deux avec
   `participations:delete`.
2. Supprimer un résultat dans le premier.
3. Supprimer **le même** dans le second.
4. **Attendu** : un message compréhensible (« Ce résultat n'existe plus. »), pas
   une erreur technique brute, et la page se remet à jour.

## Références

- Décisions et alternatives écartées : [research.md](./research.md)
- La colonne `club_locked`, ses invariants et sa migration :
  [data-model.md](./data-model.md)
- Formes exactes des trois ressources d'API : [contracts/api.md](./contracts/api.md)
- Table de visibilité et microcopie : [contracts/ui.md](./contracts/ui.md)
