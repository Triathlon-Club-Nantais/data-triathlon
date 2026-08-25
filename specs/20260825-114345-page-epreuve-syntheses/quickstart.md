# Quickstart — vérifier le lot #486

Comment prouver que la page épreuve dit ce qu'elle omet, signale ce qui est douteux, et
mène au classement. Chaque section correspond à une histoire de la spec et se vérifie
**sans** les deux autres.

## Prérequis

```bash
# Backend — aucun venv à activer, uv s'en charge
cd backend
uv sync
uv run alembic upgrade head        # aucune migration nouvelle dans ce lot
uv run python scripts/dev_server.py   # publie un port libre, le front le lit

# Frontend, dans un second terminal
cd frontend
npm install
npm run dev
```

Le backend prend un **port éphémère** et le publie dans `.dev-backend.json` à la racine du
worktree (`docs/dev-multi-worktree.md`). Les `curl` ci-dessous supposent `$API` résolu :

```bash
export API="$(jq -r .url .dev-backend.json)"
```

> ⚠ **L'API de lecture est gardée par le mot de passe du site** (#509, #526), et la garde
> est *fail-closed* : un `curl` nu rend `401 Vous devez être connecté…`, pas les données.
> Deux façons de dérouler ce qui suit :
>
> - **par le navigateur**, en passant d'abord `/acces` — c'est le chemin réel du visiteur,
>   et le seul qui vérifie aussi le rendu ;
> - **hors réseau**, en montant l'app avec la garde neutralisée, ce qui vérifie les champs
>   publiés sans se battre avec l'authentification :
>
> ```python
> app = create_app()
> app.dependency_overrides[require_site_access] = lambda: None
> client = TestClient(app)
> ```
>
> Vérifier aussi que la base de dev est à jour (`uv run alembic upgrade head`) : une
> migration arrivée sur `main` la laisse sinon sur `no such column`.

Base de dev : `backend/triathlon.db`, 72 épreuves et 11 629 participations. Les identifiants
d'épreuve cités ci-dessous en viennent — sauf la course 214, qui est le cas de l'audit et
vit en **production**, figée ici en fixture de test.

## Les suites, en premier

```bash
cd backend  && uv run pytest -m "not integration"   # 4 workers ; -n 0 pour séquentiel
cd backend  && uv run ruff check .
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build                        # strict TS + RSC
```

`rtk uv run pytest -m "not integration"` rend la même preuve pour ~99 % de tokens en moins.
**Jamais** sur le sondage ci-dessous, ni sur `alembic`.

---

## US1 — la fiabilité affichée

### Le signal d'épreuve et le marqueur de ligne

```bash
# Une épreuve dont les inters ne couvrent pas tout le parcours (médiane +11,4 %)
curl -s "$API/api/v1/courses/65/summary" | jq '.split_gap_median'
# → ~0.114 : la page doit dire, UNE fois, que les inters ne couvrent pas le parcours

# Une épreuve dont les inters collent au total
curl -s "$API/api/v1/courses/8/summary" | jq '.split_gap_median'
# → proche de 0 : aucun signal d'épreuve

# L'écart d'une ligne, publié et signé
curl -s "$API/api/v1/courses/47?page_size=5" | jq '.participations[].split_gap_ratio'
```

**À l'écran** (`/courses/65`) : une mention en tête de page, et **aucun** marqueur sur les
lignes — c'est tout l'enjeu du sondage. Les treize lignes de l'épreuve 66 s'écartent
toutes du même ordre : le dire treize fois serait du bruit.

**À l'écran** (`/courses/47`, 681 finishers) : aucune ligne marquée non plus. Le seuil de
2 % proposé par l'audit en aurait marqué **285**, sur une épreuve que le produit tient pour
fiable.

### Le cas que la règle doit capter

Il n'est pas dans la base de dev — c'est l'angle mort assumé du sondage. Il vit en fixture :

```bash
cd backend && uv run pytest tests/test_core/test_split_gap.py -k "course_214" -v
```

La ligne figée : 31 s + 34 s + 19 min 18 s pour un total de 1 h 06 min 18 s, soit **69,3 %
d'écart**. Si ce test tombe, la règle a cessé de capter ce pour quoi elle a été écrite.

### La marque « données douteuses »

```bash
curl -s "$API/api/v1/courses/events?page_size=5" | jq '.items[] | {id, is_reliable, quality_issues}'
```

**À l'écran** : sur `/resultats`, les épreuves à anomalies portent une marque ; sur
`/courses/[id]`, l'en-tête porte la même, et son détail énumère les anomalies **dans les
mêmes mots** que le profil athlète — le vocabulaire vient de `frontend/lib/quality.ts`,
qui ne doit pas se dédoubler.

**Le cas normal est l'absence** : une épreuve saine n'affiche rien. Un écran qui marque
tout ne marque plus rien.

---

## US2 — la franchise des répartitions

```bash
curl -s "$API/api/v1/courses/47/summary" \
  | jq '{affichees: (.categories | length), total: .categories_total,
         somme: ([.categories[].count] | add),
         clubs_affiches: (.clubs | length), clubs_total}'
```

**À l'écran** (`/courses/47`) :

1. La somme des parts affichées vaut **100 %**, part « Autres (N) » comprise — c'est
   `SC-001`, et le cas mesuré à 86,1 % sur la course 214 ne doit se reproduire nulle part.
2. La carte « Top clubs » porte un pied « et N autres clubs », avec
   `N = clubs_total − clubs.length`.
3. Les titres énoncent leur portée, pas un tout.

**Le cas de la liste vide** — une épreuve sans club renseigné : l'en-tête « Club /
Athlètes » **disparaît**, seul l'état d'absence reste. C'est le défaut constaté sur la
course 340.

**Le cas du reste nul** — une épreuve dont toutes les catégories tiennent dans les huit
barres : **aucune** part « Autres ». Un reste nul ne se dessine pas.

**Au lecteur d'écran** : la description de la carte inclut la part « Autres » et le nombre
de clubs non listés, au même titre que ce qui est dessiné.

---

## US3 — les synthèses navigables

```bash
# Filtre club, égalité exacte
curl -s "$API/api/v1/courses/47?club=TRIATHLON%20CLUB%20NANTAIS" | jq '.total'

# Filtre catégorie
curl -s "$API/api/v1/courses/47?category=V2" | jq '.total'

# Cumul des quatre restrictions
curl -s "$API/api/v1/courses/47?category=V2&q=du&scope=club&page_size=5" | jq '.total'

# Valeur inconnue : sélection vide, jamais un 404
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/v1/courses/47?club=CLUB%20INEXISTANT"
# → 200
```

**À l'écran** :

1. Une ligne de club activée mène au classement filtré, en **une seule activation**
   (`SC-007`).
2. Une part de catégorie fait de même.
3. Un repère nommant la valeur apparaît, **retirable indépendamment** des autres
   sélections — il se pose sur le motif livré par le lot #485, il ne le réécrit pas.
4. La ligne d'état annonce le nombre de résultats face au total de l'épreuve.
5. Une sélection vide nomme **le filtre en cause** et offre le retour au classement
   entier. Elle ne parle jamais de « recherche » quand aucune recherche n'est active —
   c'est le défaut constaté sur `/courses/340?scope=club`.
6. Le compteur de la carte et le total du classement **coïncident** : c'est ce que
   l'égalité exacte garantit, et ce qu'une comparaison partielle casserait.

**Le lien partagé** (`SC-009`) : copier l'URL d'un classement filtré et l'ouvrir dans une
fenêtre privée doit restituer exactement la même sélection.

**Les libellés de catégorie** (`SC-008`) : le libellé complet de « PoM » doit s'obtenir
sans quitter la page, **au doigt et au clavier** — pas seulement au survol. Le patron
existe : `CelluleInter` de `RaceFinishers.tsx` combine `role="img"`, `title` et
`aria-label` pour le marqueur posé par #472.

Un code hors table s'affiche **tel quel**, sans libellé inventé.

---

## L'additivité du contrat (`SC-010`)

Le critère n'est pas « les tests passent » mais « les tests passent **sans qu'une
assertion ait été modifiée** » :

```bash
cd backend && git diff --stat origin/main -- tests/test_api/
```

Un appel sans les nouveaux paramètres doit rendre une réponse identique aux clés
d'origine. Six champs sont ajoutés, aucun retiré, aucune sémantique inversée.

---

## Ce que le déroulé a effectivement montré (2026-08-25)

Mesuré sur la base de dev, garde neutralisée :

| Vérification | Attendu | Constaté |
| --- | --- | --- |
| c8 — filtre club `Usc caen triathlon` | le compte de la carte | **13 = 13** |
| c8 — filtre `category=S2` | le compte de la carte | **215 = 215** |
| c8 — ligne TCN (via `scope=club`) | le compte TCN de la carte | **15 = 15** |
| c8 — cumul club + catégorie | intersection | 1 |
| c8 — `club=CLUB INEXISTANT` | 200 et sélection vide | **HTTP 200, total 0** |
| c27 — barre « Autres » | le reste des catégories | **Autres (163)** sur 546 |
| c8 — pied des clubs | `clubs_total − 9` | **« et 164 autres clubs »** |
| c47 — aucun club renseigné | en-tête masqué | **0/0, pas de pied** |
| c47 — médiane d'écart | > 1 %, donc note d'épreuve | **+1,69 % sur 681 lignes** |
| c8, c65 — médiane d'écart | < 1 %, donc silence | **+0,07 % et +0,34 %** |
| Réponse sans les nouveaux paramètres | clés inchangées | `course, page, page_size, participations, total` |

La troisième ligne est celle qui compte : elle vérifie le correctif de la revue de code.
La carte fusionne les orthographes du TCN sous un libellé canonique qu'**aucune** ligne ne
porte en base — un `?club=` en égalité exacte y rendait 0 sous une carte annonçant 15.

## Re-sonder les seuils

Les seuils de la règle d'écart sont calés sur la base de **dev**, qui ne contient aucune
ligne réellement fausse : zéro fausse alerte y est mesuré, la captation ne l'est pas. Avant
de les tenir pour calibrés, les re-mesurer sur la base de production, avec la méthode et
les scripts décrits dans
[`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`](../../../docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md).

Ce sondage **prime** sur la spec et sur le plan : si la production dit autre chose, c'est
la production qui a raison, et le seuil se retranche en re-sondant.
