# Quickstart : valider le découpage des relais nommés (#895)

Prérequis : worktree de `895-relay-name-split` (basé sur `epic/889-relais`, #997
incluse), `cd backend && uv sync`.

## 1. Tests automatiques (sans réseau)

```bash
cd backend
uv run pytest tests/test_scrapers_utils.py -k relay_teammates   # règle, valeurs réelles du sondage
uv run pytest tests/test_services/test_import_service.py -k relay  # _Persister : import, rescrape, garde
uv run pytest -k "relay and (oktime or chronoplace or chronoweb or sporthive)"  # fixtures fournisseurs
uv run pytest -m "not integration"                                 # suite complète
uv run ruff check .
```

Attendu : tout vert (seul `test_cors_origins_defaut`, déjà rouge sur `main`, peut
échouer).

## 2. Contrôle manuel sur base de dev (SQLite)

1. `uv run alembic upgrade head` (la base de dev copiée n'a pas encore la migration de
   #997), puis `uv run python scripts/dev_server.py` et, dans `frontend/`, `npm run dev`.
2. Importer une épreuve timepulse ou klikego à relais nommés déjà présente en base
   (sondage : SwimRun Côte Beauté 2025 pour klikego, épreuve 3232 pour timepulse) par
   l'écran d'import.
3. Vérifier :
   - la fiche d'un équipier (ex. « MASSONNEAU PIERRE ») affiche le résultat de relais,
     avec le nom d'équipe et ses équipiers ;
   - l'ancienne fiche « MASSONNEAU PIERRE / BESANCON FABIEN . » n'existe plus ;
   - une équipe « LE BRAS LUC / LE PAGE GUULLAUME . » et les groupes (« TEAM GV ») restent
     des fiches d'équipe, attribuables par « Attribuer aux équipiers » ;
   - le binôme individuel « CHAIGNEAU BENJAMIN / LENOIR-LEDOUX CHRISTELLE . » est
     inchangé.
4. Relancer l'import : le rapport ne signale aucune création, aucune fiche n'apparaît.

## 3. Critères de succès

| Critère | Vérifié par |
| --- | --- |
| SC-001, SC-002 | tests de la règle sur les valeurs du sondage + étape 2.3 |
| SC-003 | test « hors relais intact » + binôme individuel à l'étape 2.3 |
| SC-004 | test de rescrape idempotent + étape 2.4 |
| SC-005 | non vérifiable sans la prod (fiche 102324 non observée) : à contrôler après déploiement |
