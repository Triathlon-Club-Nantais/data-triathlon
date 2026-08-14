# Quickstart — vérifier la saisie manuelle des résultats (#270)

**Feature** : `20260814-130052-saisie-manuelle-resultats` · **Date** : 2026-08-14

Guide de **vérification**, pas d'implémentation. Chaque scénario correspond à un
critère d'acceptation de [spec.md](./spec.md) et dit ce qu'on doit observer.

## Prérequis

```bash
# Backend — aucun venv à activer
cd backend
uv sync
uv run alembic upgrade head          # applique la migration de la feature
uv run python scripts/reset_db.py    # base dev SQLite vierge + seed démo

# Frontend
cd ../frontend
npm install
```

Le backend prend le premier port libre à partir de 8001 et le publie ; le
frontend le lit. Rien à configurer même avec plusieurs worktrees ouverts
(`docs/dev-multi-worktree.md`).

---

## 1. La suite automatisée

C'est le passage obligé — le Principe III interdit d'annoncer quoi que ce soit
avant ces deux commandes vertes.

```bash
cd backend  && uv run pytest -m "not integration"
cd frontend && npm test
```

Vérifications ciblées pendant le développement :

```bash
cd backend
uv run pytest tests/test_api/test_participations_api.py -v      # contrat d'entrée/sortie
uv run pytest tests/test_repositories -k pending -v             # les 5 sites d'exclusion
uv run pytest tests/test_migrations.py -v                       # la migration s'applique

cd frontend
npm test -- ManualResultForm                                    # validations conditionnelles
```

Lint et build, avant toute annonce de complétion :

```bash
cd backend  && uv run ruff check .
cd frontend && npm run lint && npm run build
```

---

## 2. La migration s'applique et se remonte

```bash
cd backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

**Attendu** : aucune erreur dans les deux sens. Les quatre colonnes de
[data-model.md](./data-model.md) apparaissent, `is_pending_validation` avec un
`server_default` — donc **aucune** ligne existante marquée pendante :

```bash
uv run python -c "
from app.core.database import SessionLocal
from app.models.participation import Participation
db = SessionLocal()
print('pendantes :', db.query(Participation).filter_by(is_pending_validation=True).count())
print('total     :', db.query(Participation).count())
"
```

**Attendu** : `pendantes : 0`, total inchangé par rapport à avant migration.

---

## 3. Le formulaire refuse une saisie incomplète (US1)

```bash
cd backend  && uv run python scripts/dev_server.py     # note le port publié
cd frontend && npm run dev
```

Ouvrir `/ajouter`, atteindre le formulaire de saisie manuelle, cliquer
**Enregistrer le résultat** sans rien remplir.

**Attendu** :
- un message sous **chacun** des quatre champs obligatoires — nom, prénom, date,
  nom de l'épreuve (SC-002) ;
- aucune requête `POST /participations` émise (onglet Réseau) ;
- **aucun** champ Genre, Club ni Catégorie à l'écran (scénario 3 de US1) ;
- le champ épreuve est libellé « Nom de l'épreuve », pas « Épreuve ».

Remplir les quatre, soumettre.

**Attendu** : `201`, confirmation affichée.

---

## 4. La discipline et son format (US3)

Dans le sélecteur de discipline, **attendu** : les huit disciplines FFTri de
FR-006 sont proposées.

| Geste | Attendu |
| --- | --- |
| Choisir « Triathlon » | un choix XS / S / M / L / XL / Autre apparaît |
| Choisir « Autre » puis soumettre à vide | message d'erreur, soumission bloquée |
| Choisir « Aquathlon » | le choix de format apparaît aussi (il n'existait pour aucun aquathlon avant) |
| Choisir « Raid Multisport » | **pas** de choix de format, un champ de distance totale à la place |
| Choisir « Swim Bike » puis regarder l'encart temps | pas de champ « Course à pied » |

Ce dernier point est le piège de research.md D3 : si `swim-bike` n'a pas été
déclaré comme base multi-mots, `swim-bike-m` est lu comme la base `swim`, retombe
sur le gabarit par défaut, et une course à pied apparaît sur une discipline qui
n'en a pas.

---

## 5. Individuel / collectif, temps, lien (US4)

| Geste | Attendu |
| --- | --- |
| Écran à l'ouverture | « individuel » présélectionné |
| Passer à « collectif » | un champ « nom de l'équipe » apparaît, obligatoire |
| Soumettre en collectif sans nom d'équipe | message d'erreur, soumission bloquée |
| Repasser à « individuel » et soumettre | aucun nom d'équipe conservé, enregistrement OK |
| Soumettre avec tous les champs de temps vides | enregistrement OK (les temps sont facultatifs) |
| Choisir « abandon », sans temps ni place | enregistrement OK (FR-025) |

**Vérification en base du collectif** — il crée une épreuve distincte du solo
(research.md D6), ce qui surprend si on ne l'attend pas :

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.models.course import Course
db = SessionLocal()
for c in db.query(Course).order_by(Course.id.desc()).limit(5):
    print(c.id, c.name, c.event_type, 'relais' if c.is_relay else 'solo', c.format_label)
"
```

---

## 6. Le résultat est marqué, et ne compte nulle part (US2) — **le scénario central**

Le plus important du guide : c'est lui qui vérifie l'arbitrage Q1.

**Avant la saisie**, relever les compteurs :

```bash
PORT=<port publié>
curl -s "localhost:$PORT/api/v1/stats?scope=club" | head -c 400
curl -s "localhost:$PORT/api/v1/courses/<id>/summary" | head -c 400
```

Saisir un résultat au nom d'un athlète **déjà connu** de la base de démo, sur une
épreuve **déjà existante**.

**Attendu, dans l'ordre** :

1. **Fiche athlète** `/athletes/<id>` — le résultat y **figure**, avec une
   mention visuelle explicite d'attente de validation, distincte des autres
   lignes (SC-003 : reconnaissable sans survol ni clic).
2. **Tableau de bord** `/dashboard` — statistiques **inchangées**.
3. **Page club** `/club` — compteurs et podiums **inchangés**.
4. **Classement de l'épreuve** `/courses/<id>` — le résultat **n'y figure pas**,
   et le total de la page n'a pas bougé.
5. **Page résultats** `/resultats` — le résultat n'y figure pas.
6. **Page épreuves** et **carte** — le compteur de participants de l'épreuve n'a
   pas bougé.
7. **`course_finishers`** sur la fiche athlète — la taille annoncée du classement
   n'a pas bougé.

Rejouer les deux `curl` ci-dessus : **attendu**, réponses identiques au premier
relevé (SC-006, zéro écart).

**Contre-épreuve** — le résultat validé doit compter (scénario 6 de US2). Comme
l'écran bénévole appartient à #271, la bascule se provoque à la main :

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.models.participation import Participation
db = SessionLocal()
p = db.query(Participation).order_by(Participation.id.desc()).first()
p.is_pending_validation = False
db.commit()
print('validé :', p.id)
"
```

Recharger les sept surfaces : **attendu**, le résultat apparaît et compte partout.

---

## 7. Le lien de vérification n'est pas une source

Après une saisie portant un lien, **attendu** :

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.models.course import Course
db = SessionLocal()
c = db.query(Course).order_by(Course.id.desc()).first()
print('sources :', len(c.sources), '| provider :', repr(c.provider))
"
```

**Attendu** : `sources : 0`, `provider : ''`. Si une source apparaît, D5 a été
enfreint et `rescrape-db` tentera de scraper la page collée par le membre.

Vérifier aussi qu'un lien non exploitable (`pas une url`, `javascript:alert(1)`)
est **enregistré** mais rendu en texte brut, jamais en `<a>` cliquable.

---

## 8. Non-régression de l'import

La feature touche `mapping.participation_fields` et le repository, tous deux sur
le chemin d'import. À vérifier avant de conclure :

```bash
cd backend
uv run pytest tests/test_services -v
uv run pytest -m integration -k "klikego or raceresult"   # réseau réel, hors CI
```

**Attendu** : un résultat importé porte `is_pending_validation = False` et
apparaît normalement dans toutes les surfaces (FR-017, scénario 3 de US2).

---

## Ce que ce guide ne couvre pas

- **L'écran de validation bénévole** — issue #271. Le §6 provoque la bascule en
  base précisément parce que l'interface n'existe pas encore.
- **La vérification sur PostgreSQL** — la suite tourne sur SQLite. Le
  `server_default="false"` et les clauses d'exclusion sont portables, mais à
  reconfirmer sur preview avant mise en production, comme le fait déjà
  `specs/20260803-195212-course-pagination/quickstart.md` §10.
