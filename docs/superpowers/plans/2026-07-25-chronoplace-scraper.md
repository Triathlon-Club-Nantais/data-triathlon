# Scraper chronoplace.fr — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un provider `chronoplace.fr` qui importe, depuis une URL de classement, tous les participants de toutes les épreuves de l'événement.

**Architecture :** Un module `app/scrapers/chronoplace.py` exposant `scrape_event_all(url)`, httpx + BeautifulSoup, sans Playwright. Le site est une application Laravel + Livewire dont le composant `classement-table` synchronise ses paramètres avec l'URL : un `GET ?perPage=all` rend le classement complet (219 lignes sur l'épreuve sondée), donc ni POST `/livewire/update` ni PDF. Les colonnes varient d'une épreuve à l'autre mais chaque `<th>` porte sa clé dans `wire:click="sortBy('<clé>')"` : on lit les cellules **par clé**, jamais par position. La date de l'épreuve, absente de la page de classement, est cherchée en un GET sur l'annuaire `/recherche` — c'est un bonus, jamais un motif d'échec.

**Tech Stack :** Python 3.13, uv, httpx, BeautifulSoup (`lxml`), pytest, ruff.

**Design de référence :** `docs/superpowers/specs/2026-07-25-chronoplace-scraper-design.md` (issue [#57](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/57), sous-issue de #33).

## Global Constraints

- Toutes les commandes se lancent **depuis `backend/`**, préfixées par `uv run` (aucun venv à activer).
- Commentaires, docstrings, messages d'erreur et de log : **en français, avec accents**.
- Lint : `uv run ruff check .` doit passer (`line-length = 100`, règles `E,F,I,W,UP,B` ; `B905` impose `strict=` sur `zip()`).
- Tests unitaires **sans réseau**. Tout appel réseau réel va dans `tests/test_integration_scrapers.py` sous `@pytest.mark.integration`.
- Commits en **Conventional Commits** (`feat:`, `test:`, `docs:`…), avec `(#57)` en fin de sujet.
- Les temps restent des **chaînes** (`"01:23:45"`), normalisées via `scrapers/utils.normalize_time`.
- Le scraper ne se prononce **pas** sur le statut sportif (`status = ""`, défaut de `ScrapedResult`) : aucun label DNF/DNS/DSQ n'a été observé sur les quatre épreuves sondées, et `services/mapping.derive_status` applique alors son heuristique (finisher si temps total, sinon DNF).
- Les splits vont dans les **5 slots positionnels** de `ScrapedResult` (`swim/t1/bike/t2/run`) ; c'est `services/mapping.build_splits` qui les ré-étiquette selon `event_type`. Ne pas court-circuiter ce mécanisme.
- Nom du provider dans le registre et dans `ScrapedResult.provider` : **`chronoplace`** (exactement cette chaîne, c'est une valeur ciblable par `--provider` en CLI).

## Structure des fichiers

| Fichier | Rôle |
| --- | --- |
| `backend/app/scrapers/chronoplace.py` | **Créé.** Tout le scraper : parsing d'URL, du `wire:snapshot`, du tableau, des métadonnées, de la date, et l'orchestration `scrape_event_all`. Un seul module, comme les six providers existants (`timepulse.py`, `prolivesport.py`…). |
| `backend/app/scrapers/registry.py` | **Modifié** (~ligne 150) : ajout de `ChronoplaceProvider` et de son entrée dans `PROVIDERS`. |
| `backend/tests/test_chronoplace.py` | **Créé.** Tests unitaires, sans réseau (fixtures + `FakeClient`). |
| `backend/tests/fixtures/chronoplace_epreuve_494.html` | **Créée.** Triathlon S : splits, genre, club, `isTeam:false`. 3 lignes réelles dont une aux splits `—`. |
| `backend/tests/fixtures/chronoplace_epreuve_566.html` | **Créée.** SwimRun du même événement : colonnes `categorie`/`nb_tours`/`ecart`, catégories relais. |
| `backend/tests/fixtures/chronoplace_epreuve_493.html` | **Créée.** 24 h VTT : `isTeam:true`, noms d'équipe, temps > 24 h. |
| `backend/tests/fixtures/chronoplace_recherche_2025.html` | **Créée.** Annuaire `/recherche` réduit à 3 cartes, dont celle qui porte la date cherchée. |
| `backend/tests/test_integration_scrapers.py` | **Modifié** : URL réelle dans `LIVE_URLS` + un test dédié au lien mort. |
| `AGENTS.md` | **Modifié** : `chronoplace.fr` dans « Fournisseurs supportés ». |

Les fixtures sont des **extraits réels** du site (2026-07-25), réduits à quelques lignes : la structure conditionnelle Livewire (`<!--[if BLOCK]><![endif]-->`) et le `wire:snapshot` sont conservés tels quels, car c'est précisément ce que le parseur doit traverser.

> Le design citait l'épreuve `722` comme cas `isTeam`. Elle n'est plus servie (404 depuis) ; la fixture retenue est l'épreuve **493** (24 h VTT de Cergy 2025), qui couvre les mêmes propriétés — `isTeam:true`, noms d'équipe, aucune colonne genre/club/catégorie — et ajoute un temps > 24 h.

## Faits vérifiés sur la source (sondage du 2026-07-25)

Ces observations viennent de fetchs réels ; elles justifient des choix qui, sans elles, paraîtraient arbitraires.

1. `?perPage=all` sur `/epreuve/494` rend **219 lignes** (1,2 Mo) contre 50 par défaut.
2. `/classement/<slug>` **sans** `/epreuve/<id>` renvoie un **302** vers la première épreuve — mais la redirection **perd la query string** : `?perPage=all` serait ignoré et on ne récupérerait que 50 lignes. D'où `_resolve_epreuve_id`, qui résout l'id avant de demander le classement complet.
3. Les `<td>` sont émis sous les **mêmes conditions Livewire** que les `<th>` : sur les quatre épreuves sondées, `len(cells) == len(keys)` sur 100 % des lignes. L'alignement en-tête ↔ cellule est donc garanti, et une ligne au compte divergent est une anomalie qu'on journalise et saute.
4. Une cellule de temps vide est rendue **`—`** (tiret cadratin), et `ecart` vaut `--` ou `+5:16`. `normalize_time` laisse passer ces valeurs telles quelles → il faut un filtre explicite « ça ressemble à un temps, ou rien ».
5. La date n'est ni dans un `<time>`, ni en meta, ni en JSON-LD sur la page de classement. Sur l'annuaire `/recherche`, la carte de l'événement porte `<time datetime="2025-09-21 00:00:00">` : on lit l'attribut ISO, avec repli sur le texte français (`21 septembre 2025`) via `utils.parse_fr_date`.
6. `/recherche?module=classement&annee=2025&categorie=12` renvoie **une seule page** (3 cartes) : pas de pagination à gérer une fois le filtre de catégorie posé.
7. Un classement filtré sans résultat rend un `<tbody>` **vide** — pas de ligne « aucun résultat » à filtrer.
8. `/classement/<slug faux>/epreuve/566` → **404**. Le site exige la paire slug + id exacte.

## Limites connues et assumées

- **Nom d'équipe passé à `split_athlete_name`** : `"MENARDAIS FERDINAND / COMPAIN LENA"` donne `("MENARDAIS FERDINAND", "/ COMPAIN LENA")`. C'est le comportement de TimePulse sur ses relais ; on reste cohérent avec l'existant plutôt que d'inventer une règle propre à ce provider. Un test verrouille cette sortie.
- **`event_type` d'une épreuve VTT** : `classify_event_type("24h")` retombe sur `"triathlon"` (le classifieur ne connaît pas le VTT). Hors périmètre de cette issue — le sujet est la normalisation des types, suivie ailleurs.
- **Modal de détail par coureur**, recherche `?search=`, épreuves live : hors périmètre (cf. design).

---

## Task 1 : Squelette du module, fixtures, parsing d'URL et du `wire:snapshot`

**Files:**
- Create: `backend/app/scrapers/chronoplace.py`
- Create: `backend/tests/test_chronoplace.py`
- Create: `backend/tests/fixtures/chronoplace_epreuve_494.html`
- Create: `backend/tests/fixtures/chronoplace_epreuve_566.html`
- Create: `backend/tests/fixtures/chronoplace_epreuve_493.html`

**Interfaces:**
- Consumes : rien (première tâche).
- Produces :
  - `_parse_url(url: str) -> tuple[str, str]` → `(slug, epreuve_id)`, `epreuve_id == ""` si absent ; lève `ValueError` si l'URL n'est pas un chemin `/classement/…`.
  - `_epreuve_path(slug: str, epreuve_id: str) -> str` → chemin relatif avec `?perPage=all`.
  - `_parse_snapshot(html: str) -> dict` → le `data` du composant Livewire, tableaux déballés ; `{}` si absent ou illisible.
  - Constantes `BASE_URL`, `HEADERS`, `logger`.

- [ ] **Step 1 : Créer la fixture `chronoplace_epreuve_494.html`**

Créer `backend/tests/fixtures/chronoplace_epreuve_494.html` avec exactement ce contenu (extrait réel de `https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494?perPage=all`, réduit à 3 lignes ; la ligne `wire:snapshot` est très longue, la copier telle quelle sans la recouper) :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="description" content="Résultats Spay&#x27;cific Races 2025 - Spay&#x27;cific Triathlon S">
  <link rel="canonical" href="https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494">
</head>
<body>
  <h1 class="text-xl font-bold text-gray-900 md:text-2xl"> Spay'cific Races 2025 <span class="text-gray-500">- Spay'cific Triathlon S</span> </h1>
  <div class="mt-4 flex flex-wrap gap-2">
    <a href="/classement/spaycific-races-2025/epreuve/494">Spay&#x27;cific Triathlon S</a>
    <a href="/classement/spaycific-races-2025/epreuve/566">SwimRun</a>
  </div>
  <div wire:snapshot="{&quot;data&quot;:{&quot;epreuveId&quot;:494,&quot;isTeam&quot;:false,&quot;search&quot;:&quot;&quot;,&quot;sortField&quot;:&quot;position&quot;,&quot;sortDirection&quot;:&quot;asc&quot;,&quot;perPage&quot;:&quot;all&quot;,&quot;affichageDonnees&quot;:[{&quot;categorie&quot;:false,&quot;genre&quot;:true,&quot;club&quot;:true,&quot;nb_tours&quot;:false,&quot;clasmt_genre&quot;:false,&quot;ecart&quot;:false,&quot;dossard&quot;:true,&quot;temps&quot;:true,&quot;T_natation&quot;:true,&quot;T_velo&quot;:true,&quot;T_course_a_pied&quot;:true,&quot;T1&quot;:true,&quot;T2&quot;:true},{&quot;s&quot;:&quot;arr&quot;}],&quot;analyticsContext&quot;:[{&quot;event_slug&quot;:&quot;spaycific-races-2025&quot;,&quot;event_year&quot;:&quot;2025&quot;,&quot;event_type&quot;:&quot;Triathlon&quot;,&quot;department&quot;:&quot;72&quot;,&quot;epreuve_id&quot;:&quot;494&quot;,&quot;epreuve_name&quot;:&quot;Spay&#x27;cific Triathlon S&quot;,&quot;page_type&quot;:&quot;ranking&quot;},{&quot;s&quot;:&quot;arr&quot;}],&quot;showModal&quot;:false,&quot;selectedCoureur&quot;:null,&quot;selectedTours&quot;:[[],{&quot;s&quot;:&quot;arr&quot;}],&quot;positionsWithDetails&quot;:[[],{&quot;s&quot;:&quot;arr&quot;}],&quot;paginators&quot;:[{&quot;page&quot;:1},{&quot;s&quot;:&quot;arr&quot;}]},&quot;memo&quot;:{&quot;id&quot;:&quot;PxJSzkELpuvJKY3MJbgn&quot;,&quot;name&quot;:&quot;classement-table&quot;,&quot;path&quot;:&quot;classement\/spaycific-races-2025\/epreuve\/494&quot;,&quot;method&quot;:&quot;GET&quot;,&quot;release&quot;:&quot;a-a-a&quot;,&quot;children&quot;:[],&quot;scripts&quot;:[],&quot;assets&quot;:[],&quot;errors&quot;:[],&quot;locale&quot;:&quot;fr&quot;},&quot;checksum&quot;:&quot;54074dac41ade1aae7dff79430ff5aeefe2b4bbc5e9091951d65a020ac64c758&quot;}">
    <table>
      <thead><tr>
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('position')"><div>Position</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('dossard')"><div>Dos.</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('nom')"><div>Nom-Prenom</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('genre')"><div>Genre</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('club')"><div>Club</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('T_natation')"><div>Natation</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('T1')"><div>T1</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('T_velo')"><div>Vélo</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('T2')"><div>T2</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('T_course_a_pied')"><div>Course à pied</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('temps')"><div>Temps</div></th><!--[if ENDBLOCK]><![endif]-->
      </tr></thead>
      <tbody>
      <tr wire:click="showDetails(1)">
        <!--[if BLOCK]><![endif]--><td>1</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>90</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>MARTIN Malo</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>M</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>ENTENTE HAUTE BRETAGNE TRIATHLON</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:10:53</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:00:48</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:31:01</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:00:52</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:04:33</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>01:01:26</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      <tr wire:click="showDetails(8)">
        <!--[if BLOCK]><![endif]--><td>8</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>49</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>MASHAYEKHI Sherwin</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>M</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>TRIATHLON CLUB NANTAIS</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:13:13</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:01:06</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:32:06</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:00:49</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>00:04:49</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>01:06:55</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      <tr wire:click="showDetails(133)">
        <!--[if BLOCK]><![endif]--><td>133</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>150</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>RENOU Kevin</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>M</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td></td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>—</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>—</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>—</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>—</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>—</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>01:30:44</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      </tbody>
    </table>
  </div>
</body>
</html>
```

- [ ] **Step 2 : Créer la fixture `chronoplace_epreuve_566.html`**

Créer `backend/tests/fixtures/chronoplace_epreuve_566.html` (SwimRun du même événement — colonnes différentes, catégories relais ; noter les **doubles espaces** autour du `/` dans les noms d'équipe, ils viennent du markup réel) :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="description" content="Résultats Spay&#x27;cific Races 2025 - SwimRun">
  <link rel="canonical" href="https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/566">
</head>
<body>
  <h1 class="text-xl font-bold text-gray-900 md:text-2xl"> Spay'cific Races 2025 <span class="text-gray-500">- SwimRun</span> </h1>
  <div class="mt-4 flex flex-wrap gap-2">
    <a href="/classement/spaycific-races-2025/epreuve/494">Spay&#x27;cific Triathlon S</a>
    <a href="/classement/spaycific-races-2025/epreuve/566">SwimRun</a>
  </div>
  <div wire:snapshot="{&quot;data&quot;:{&quot;epreuveId&quot;:566,&quot;isTeam&quot;:false,&quot;search&quot;:&quot;&quot;,&quot;sortField&quot;:&quot;position&quot;,&quot;sortDirection&quot;:&quot;asc&quot;,&quot;perPage&quot;:50,&quot;affichageDonnees&quot;:[{&quot;categorie&quot;:true,&quot;genre&quot;:false,&quot;club&quot;:false,&quot;nb_tours&quot;:true,&quot;clasmt_genre&quot;:false,&quot;ecart&quot;:true,&quot;dossard&quot;:true,&quot;temps&quot;:true,&quot;T_natation&quot;:false,&quot;T_velo&quot;:false,&quot;T_course_a_pied&quot;:false,&quot;T1&quot;:false,&quot;T2&quot;:false},{&quot;s&quot;:&quot;arr&quot;}],&quot;analyticsContext&quot;:[{&quot;event_slug&quot;:&quot;spaycific-races-2025&quot;,&quot;event_year&quot;:&quot;2025&quot;,&quot;event_type&quot;:&quot;Triathlon&quot;,&quot;department&quot;:&quot;72&quot;,&quot;epreuve_id&quot;:&quot;566&quot;,&quot;epreuve_name&quot;:&quot;SwimRun&quot;,&quot;page_type&quot;:&quot;ranking&quot;},{&quot;s&quot;:&quot;arr&quot;}],&quot;showModal&quot;:false,&quot;selectedCoureur&quot;:null,&quot;selectedTours&quot;:[[],{&quot;s&quot;:&quot;arr&quot;}],&quot;positionsWithDetails&quot;:[[],{&quot;s&quot;:&quot;arr&quot;}],&quot;paginators&quot;:[{&quot;page&quot;:1},{&quot;s&quot;:&quot;arr&quot;}]},&quot;memo&quot;:{&quot;id&quot;:&quot;fwmLlBJkrxT3bQWPKZaE&quot;,&quot;name&quot;:&quot;classement-table&quot;,&quot;path&quot;:&quot;classement\/spaycific-races-2025\/epreuve\/566&quot;,&quot;method&quot;:&quot;GET&quot;,&quot;release&quot;:&quot;a-a-a&quot;,&quot;children&quot;:[],&quot;scripts&quot;:[],&quot;assets&quot;:[],&quot;errors&quot;:[],&quot;locale&quot;:&quot;fr&quot;},&quot;checksum&quot;:&quot;cdacda22a16bc9bf242220db69571fb95673f9475283dc6b1f061b5d90250be3&quot;}">
    <table>
      <thead><tr>
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('position')"><div>Position</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('dossard')"><div>Dos.</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('nom')"><div>Nom-Prenom</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('categorie')"><div>Catégorie</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('nb_tours')"><div>Nb Tours</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('temps')"><div>Temps</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('ecart')"><div>Ecart</div></th><!--[if ENDBLOCK]><![endif]-->
      </tr></thead>
      <tbody>
      <tr wire:click="showDetails(1)">
        <!--[if BLOCK]><![endif]--><td>1</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>7</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>MARTIN Nicolas</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>Solo Homme</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>15</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>02:00:20</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>--</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      <tr wire:click="showDetails(2)">
        <!--[if BLOCK]><![endif]--><td>2</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>81</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>MENARDAIS FERDINAND  /  COMPAIN LENA</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>Relais Mixte</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>15</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>02:05:37</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>+5:16</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      <tr wire:click="showDetails(3)">
        <!--[if BLOCK]><![endif]--><td>3</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>51</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>LE BOZEC HENRI  /  BABINET SYLVAIN</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>Duo Masculin</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>14</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>02:03:43</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>--</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      </tbody>
    </table>
  </div>
</body>
</html>
```

- [ ] **Step 3 : Créer la fixture `chronoplace_epreuve_493.html`**

Créer `backend/tests/fixtures/chronoplace_epreuve_493.html` (`isTeam:true`, noms d'équipe, temps > 24 h, aucune colonne genre/club/catégorie) :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="description" content="Résultats 24H VTT de CERGY 2025 - 24h">
  <link rel="canonical" href="https://www.chronoplace.fr/classement/24h-vtt-de-cergy-2025/epreuve/493">
</head>
<body>
  <h1 class="text-xl font-bold text-gray-900 md:text-2xl"> 24H VTT de CERGY 2025 <span class="text-gray-500">- 24h</span> </h1>
  <div class="mt-4 flex flex-wrap gap-2">
    <a href="/classement/24h-vtt-de-cergy-2025/epreuve/492">06h</a>
    <a href="/classement/24h-vtt-de-cergy-2025/epreuve/493">24h</a>
  </div>
  <div wire:snapshot="{&quot;data&quot;:{&quot;epreuveId&quot;:493,&quot;isTeam&quot;:true,&quot;search&quot;:&quot;&quot;,&quot;sortField&quot;:&quot;position&quot;,&quot;sortDirection&quot;:&quot;asc&quot;,&quot;perPage&quot;:&quot;all&quot;,&quot;affichageDonnees&quot;:[{&quot;categorie&quot;:false,&quot;genre&quot;:false,&quot;club&quot;:false,&quot;nb_tours&quot;:true,&quot;clasmt_genre&quot;:false,&quot;ecart&quot;:true,&quot;dossard&quot;:true,&quot;temps&quot;:true,&quot;T_natation&quot;:false,&quot;T_velo&quot;:false,&quot;T_course_a_pied&quot;:false,&quot;T1&quot;:false,&quot;T2&quot;:false},{&quot;s&quot;:&quot;arr&quot;}],&quot;analyticsContext&quot;:[{&quot;event_slug&quot;:&quot;24h-vtt-de-cergy-2025&quot;,&quot;event_year&quot;:&quot;2025&quot;,&quot;event_type&quot;:&quot;VTT&quot;,&quot;department&quot;:&quot;95&quot;,&quot;epreuve_id&quot;:&quot;493&quot;,&quot;epreuve_name&quot;:&quot;24h&quot;,&quot;page_type&quot;:&quot;ranking&quot;},{&quot;s&quot;:&quot;arr&quot;}],&quot;showModal&quot;:false,&quot;selectedCoureur&quot;:null,&quot;selectedTours&quot;:[[],{&quot;s&quot;:&quot;arr&quot;}],&quot;positionsWithDetails&quot;:[[],{&quot;s&quot;:&quot;arr&quot;}],&quot;paginators&quot;:[{&quot;page&quot;:1},{&quot;s&quot;:&quot;arr&quot;}]},&quot;memo&quot;:{&quot;id&quot;:&quot;XMwmeYmgDiNI5FDi09Pp&quot;,&quot;name&quot;:&quot;classement-table&quot;,&quot;path&quot;:&quot;classement\/24h-vtt-de-cergy-2025\/epreuve\/493&quot;,&quot;method&quot;:&quot;GET&quot;,&quot;release&quot;:&quot;a-a-a&quot;,&quot;children&quot;:[],&quot;scripts&quot;:[],&quot;assets&quot;:[],&quot;errors&quot;:[],&quot;locale&quot;:&quot;fr&quot;},&quot;checksum&quot;:&quot;302d4091f2bcf2b85db9a843723c11f9749b360b0bcf98676fc0ca1c23216d0c&quot;}">
    <table>
      <thead><tr>
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('position')"><div>Position</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('dossard')"><div>Dos.</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('nom')"><div>Équipe</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('nb_tours')"><div>Nb Tours</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('temps')"><div>Temps</div></th><!--[if ENDBLOCK]><![endif]-->
      <!--[if BLOCK]><![endif]--><th scope="col" wire:click="sortBy('ecart')"><div>Ecart</div></th><!--[if ENDBLOCK]><![endif]-->
      </tr></thead>
      <tbody>
      <tr wire:click="showDetails(1)">
        <!--[if BLOCK]><![endif]--><td>1</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>519</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>CREPHAISSON</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>95</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>23:59:53</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>--</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      <tr wire:click="showDetails(4)">
        <!--[if BLOCK]><![endif]--><td>4</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>618</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>LA ROUE LA VRAIE</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>88</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>24:00:13</td><!--[if ENDBLOCK]><![endif]-->
        <!--[if BLOCK]><![endif]--><td>--</td><!--[if ENDBLOCK]><![endif]-->
      </tr>
      </tbody>
    </table>
  </div>
</body>
</html>
```

- [ ] **Step 4 : Écrire les tests qui échouent**

Créer `backend/tests/test_chronoplace.py` :

```python
"""
Tests unitaires pour scrapers/chronoplace.py (sans réseau).

Les fixtures sont des extraits réels du site (2026-07-25), réduits à quelques
lignes : structure conditionnelle Livewire et `wire:snapshot` conservés tels quels.
"""
from pathlib import Path

import pytest

from app.scrapers import chronoplace

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EPREUVE_494 = _fixture("chronoplace_epreuve_494.html")   # triathlon S, splits
EPREUVE_566 = _fixture("chronoplace_epreuve_566.html")   # swimrun, catégories relais
EPREUVE_493 = _fixture("chronoplace_epreuve_493.html")   # 24h VTT, isTeam


def test_parse_url_avec_epreuve():
    slug, epreuve_id = chronoplace._parse_url(
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494"
    )
    assert (slug, epreuve_id) == ("spaycific-races-2025", "494")


def test_parse_url_slug_seul():
    """URL sans /epreuve/<id> : acceptée, l'id sera résolu par une requête."""
    slug, epreuve_id = chronoplace._parse_url(
        "https://www.chronoplace.fr/classement/spaycific-races-2025"
    )
    assert (slug, epreuve_id) == ("spaycific-races-2025", "")


def test_parse_url_ignore_la_query_string():
    slug, epreuve_id = chronoplace._parse_url(
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494?perPage=all"
    )
    assert (slug, epreuve_id) == ("spaycific-races-2025", "494")


def test_parse_url_rejette_une_page_hors_classement():
    with pytest.raises(ValueError, match="non reconnue"):
        chronoplace._parse_url("https://www.chronoplace.fr/recherche?module=classement")


def test_epreuve_path_force_le_classement_complet():
    """`perPage=all` est ce qui fait passer de 50 lignes au classement entier."""
    assert chronoplace._epreuve_path("spaycific-races-2025", "494") == (
        "/classement/spaycific-races-2025/epreuve/494?perPage=all"
    )


def test_parse_snapshot_deballe_les_tableaux_livewire():
    """Livewire sérialise une liste en `[valeur, {"s": "arr"}]` → on prend l'élément 0."""
    data = chronoplace._parse_snapshot(EPREUVE_494)

    assert data["epreuveId"] == 494
    assert data["isTeam"] is False
    assert data["analyticsContext"]["epreuve_name"] == "Spay'cific Triathlon S"
    assert data["analyticsContext"]["event_year"] == "2025"
    assert data["affichageDonnees"]["T_natation"] is True


def test_parse_snapshot_is_team():
    assert chronoplace._parse_snapshot(EPREUVE_493)["isTeam"] is True


def test_parse_snapshot_page_sans_composant():
    assert chronoplace._parse_snapshot("<html><body>rien</body></html>") == {}


def test_parse_snapshot_json_illisible():
    assert chronoplace._parse_snapshot('<div wire:snapshot="{pas du json">x</div>') == {}
```

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v
```

Attendu : erreur de collecte `ImportError: cannot import name 'chronoplace' from 'app.scrapers'`.

- [ ] **Step 6 : Écrire l'implémentation minimale**

Créer `backend/app/scrapers/chronoplace.py` :

```python
"""
Scraper chronoplace.fr — chronométreur sarthois, application Laravel + Livewire.

URL de classement :
  https://www.chronoplace.fr/classement/<slug>/epreuve/<id>

Le composant Livewire `classement-table` synchronise ses paramètres avec l'URL
(son `wire:effects` déclare `search`, `sortField`, `perPage`, `page`) : un simple
`GET ?perPage=all` rend le classement complet (219 lignes sur l'épreuve sondée,
contre 50 par défaut). D'où ni POST `/livewire/update` — dont le snapshot et le
checksum seraient à re-signer à chaque déploiement du site — ni parsing du PDF
de classement.

Flux (cf. docs/superpowers/specs/2026-07-25-chronoplace-scraper-design.md) :
  1. `_parse_url`        → (slug, epreuve_id)
  2. `_fetch`            → GET de l'épreuve avec `?perPage=all`
  3. `_parse_snapshot`   → isTeam + analyticsContext (année, type, nom d'épreuve)
  4. `_parse_table`      → une ligne = {clé de colonne → cellule}, lues **par clé**
                           (`sortBy('...')` du `<th>`), jamais par position
  5. `_fetch_event_date` → 1 GET sur l'annuaire /recherche (la date est absente
                           de la page de classement)
  6. les épreuves sœurs de l'événement (onglets) sont importées elles aussi
"""
import json
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.chronoplace.fr"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_URL_RE = re.compile(r"^/classement/(?P<slug>[^/]+)(?:/epreuve/(?P<id>\d+))?/?$")


def _parse_url(url: str) -> tuple[str, str]:
    """(slug, id d'épreuve). L'id est "" si l'URL ne pointe que l'événement."""
    m = _URL_RE.match(urlparse(url).path)
    if not m:
        raise ValueError(f"URL chronoplace.fr non reconnue : {url}")
    return m.group("slug"), m.group("id") or ""


def _epreuve_path(slug: str, epreuve_id: str) -> str:
    """Chemin du classement **complet** d'une épreuve."""
    return f"/classement/{slug}/epreuve/{epreuve_id}?perPage=all"


def _unwrap(value):
    """Déballe un tableau sérialisé par Livewire : `[valeur, {"s": "arr"}]` → valeur."""
    if (
        isinstance(value, list) and len(value) == 2
        and isinstance(value[1], dict) and value[1].get("s") == "arr"
    ):
        return value[0]
    return value


def _parse_snapshot(html: str) -> dict:
    """Le `data` du composant `classement-table`, tableaux déballés.

    Préféré aux attributs `data-track-*` dispersés dans le markup : tout y est
    déjà structuré (isTeam, inventaire des colonnes, contexte analytics).
    """
    el = BeautifulSoup(html, "lxml").find(attrs={"wire:snapshot": True})
    if not el:
        return {}
    try:
        data = json.loads(el["wire:snapshot"]).get("data", {})
    except (json.JSONDecodeError, TypeError):
        logger.warning("wire:snapshot illisible")
        return {}
    return {key: _unwrap(value) for key, value in data.items()}
```

- [ ] **Step 7 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py -v
uv run ruff check app/scrapers/chronoplace.py tests/test_chronoplace.py
```

Attendu : 9 tests PASS, ruff « All checks passed! ».

- [ ] **Step 8 : Commit**

```bash
git add app/scrapers/chronoplace.py tests/test_chronoplace.py tests/fixtures/chronoplace_epreuve_*.html
git commit -m "feat(scrapers): squelette chronoplace — URL et wire:snapshot (#57)"
```

---

## Task 2 : Lecture du tableau par clé de colonne

Les colonnes affichées changent d'une épreuve à l'autre (le triathlon a 11 colonnes, le swimrun 7, le 24 h VTT 6) et l'ordre n'est pas stable : sur l'épreuve 494, `temps` est la **dernière** colonne, après les cinq splits. Lire par position casserait au premier changement d'affichage ; on construit donc `{index → clé}` depuis le `thead`.

**Files:**
- Modify: `backend/app/scrapers/chronoplace.py`
- Test: `backend/tests/test_chronoplace.py`

**Interfaces:**
- Consumes : les fixtures et le module de la Task 1.
- Produces :
  - `_column_keys(table) -> list[str]` — table = élément bs4 `<table>` ; une entrée par `<th>`, `""` si le `<th>` ne porte pas de `sortBy`.
  - `_parse_table(html: str) -> list[dict[str, str]]` — une ligne = `{clé de colonne: texte de cellule}`.
  - `_time_or_empty(raw: str) -> str` — temps normalisé, ou `""` si la valeur n'est pas un temps.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_chronoplace.py` :

```python
def test_parse_table_lit_les_colonnes_par_cle():
    """Le `temps` est la dernière colonne, après les splits : lire par position casserait."""
    rows = chronoplace._parse_table(EPREUVE_494)

    assert len(rows) == 3
    assert rows[0] == {
        "position": "1",
        "dossard": "90",
        "nom": "MARTIN Malo",
        "genre": "M",
        "club": "ENTENTE HAUTE BRETAGNE TRIATHLON",
        "T_natation": "00:10:53",
        "T1": "00:00:48",
        "T_velo": "00:31:01",
        "T2": "00:00:52",
        "T_course_a_pied": "00:04:33",
        "temps": "01:01:26",
    }


def test_parse_table_colonnes_differentes_selon_lepreuve():
    """Le swimrun n'a ni genre ni club, mais une catégorie, un nb de tours et un écart."""
    rows = chronoplace._parse_table(EPREUVE_566)

    assert len(rows) == 3
    assert set(rows[0]) == {"position", "dossard", "nom", "categorie", "nb_tours", "temps", "ecart"}
    assert rows[1]["categorie"] == "Relais Mixte"
    assert rows[1]["ecart"] == "+5:16"


def test_parse_table_epreuve_sans_dossard_ni_categorie():
    rows = chronoplace._parse_table(EPREUVE_493)

    assert [r["nom"] for r in rows] == ["CREPHAISSON", "LA ROUE LA VRAIE"]
    assert "categorie" not in rows[0]


def test_parse_table_page_sans_tableau():
    assert chronoplace._parse_table("<html><body>rien</body></html>") == []


def test_parse_table_ignore_une_ligne_desalignee():
    """Anomalie jamais observée sur les 4 épreuves sondées, mais on ne décale rien."""
    html = """
    <table>
      <thead><tr>
        <th wire:click="sortBy('position')">P</th>
        <th wire:click="sortBy('nom')">N</th>
      </tr></thead>
      <tbody>
        <tr><td>1</td><td>MARTIN Malo</td></tr>
        <tr><td colspan="2">Aucun résultat</td></tr>
      </tbody>
    </table>
    """
    rows = chronoplace._parse_table(html)

    assert rows == [{"position": "1", "nom": "MARTIN Malo"}]


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("00:10:53", "00:10:53"),
        ("5:16", "00:05:16"),        # MM:SS → HH:MM:SS
        ("24:00:13", "24:00:13"),    # 24h VTT : durée > 24 h conservée telle quelle
        ("—", ""),                   # cellule de split vide (tiret cadratin)
        ("--", ""),                  # écart nul
        ("+5:16", ""),               # écart : ni temps ni split
        ("", ""),
    ],
)
def test_time_or_empty(brut, attendu):
    assert chronoplace._time_or_empty(brut) == attendu
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v -k "parse_table or time_or_empty"
```

Attendu : FAIL avec `AttributeError: module 'app.scrapers.chronoplace' has no attribute '_parse_table'`.

- [ ] **Step 3 : Écrire l'implémentation**

Dans `backend/app/scrapers/chronoplace.py`, ajouter l'import de `normalize_time` sous les imports existants :

```python
from .utils import normalize_time
```

Ajouter les deux regex sous `_URL_RE` :

```python
_SORT_RE = re.compile(r"sortBy\('([^']+)'\)")
# Ce à quoi doit ressembler une valeur pour être prise pour un temps. Le site
# rend « — » sur un split vide et « -- » / « +5:16 » dans la colonne d'écart :
# `normalize_time` les laisse passer tels quels, il faut donc filtrer ici.
_TIME_RE = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")
```

Ajouter à la fin du module :

```python
def _column_keys(table) -> list[str]:
    """Clé de chaque colonne, lue dans `wire:click="sortBy('<clé>')"` du `<th>`.

    Vocabulaire fermé : position, dossard, nom, genre, club, categorie,
    clasmt_genre, nb_tours, ecart, temps, T_natation, T1, T_velo, T2,
    T_course_a_pied. Un `<th>` sans `sortBy` occupe une place vide pour ne pas
    décaler les colonnes suivantes.
    """
    keys = []
    for th in table.select("thead th"):
        m = _SORT_RE.search(th.get("wire:click") or "")
        keys.append(m.group(1) if m else "")
    return keys


def _parse_table(html: str) -> list[dict[str, str]]:
    """Lignes du classement : une ligne = {clé de colonne → texte de la cellule}.

    `thead` et `tbody` partagent les mêmes conditions d'affichage Livewire
    (`<!--[if BLOCK]-->`), donc l'alignement en-tête ↔ cellule est garanti ; une
    ligne au compte divergent est une anomalie, journalisée et sautée plutôt
    que décalée.
    """
    table = BeautifulSoup(html, "lxml").find("table")
    if table is None:
        return []
    keys = _column_keys(table)
    if not any(keys):
        return []
    rows = []
    for tr in table.select("tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) != len(keys):
            logger.warning("Ligne ignorée : %d cellules pour %d colonnes", len(cells), len(keys))
            continue
        rows.append({key: value for key, value in zip(keys, cells, strict=True) if key})
    return rows


def _time_or_empty(raw: str) -> str:
    """Temps normalisé, ou "" si la valeur n'en est pas un."""
    normalized = normalize_time((raw or "").strip())
    return normalized if _TIME_RE.match(normalized) else ""
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py -v
uv run ruff check app/scrapers/chronoplace.py tests/test_chronoplace.py
```

Attendu : 21 tests PASS (9 + 12), ruff OK. Si `B905 zip() without an explicit strict=` apparaît, c'est que le `strict=True` a été oublié.

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/chronoplace.py tests/test_chronoplace.py
git commit -m "feat(scrapers): chronoplace lit le tableau par clé de colonne (#57)"
```

---

## Task 3 : Métadonnées de l'épreuve — nom, épreuves sœurs, type, relais

**Files:**
- Modify: `backend/app/scrapers/chronoplace.py`
- Test: `backend/tests/test_chronoplace.py`

**Interfaces:**
- Consumes : Task 1 et 2.
- Produces :
  - `_event_name(html: str, slug: str) -> str` — `<h1>`, repli meta `description`, repli slug en Title Case.
  - `_list_epreuves(html: str, slug: str) -> list[str]` — ids des onglets de l'événement, dans l'ordre du document, dédoublonnés.
  - `_event_type(analytics: dict, event_name: str) -> str` — slug canonique (`triathlon-s`, `swimrun`…).
  - `_is_relay_category(category: str) -> bool`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_chronoplace.py` :

```python
def test_event_name_depuis_le_h1():
    """Le nom de l'épreuve doit figurer dans le nom de Course : `uq_course_identity`
    porte sur (name, event_date, event_type, is_relay), donc deux épreuves d'un même
    événement classées dans le même type fusionneraient sous le seul nom d'événement."""
    assert chronoplace._event_name(EPREUVE_494, "spaycific-races-2025") == (
        "Spay'cific Races 2025 - Spay'cific Triathlon S"
    )
    assert chronoplace._event_name(EPREUVE_566, "spaycific-races-2025") == (
        "Spay'cific Races 2025 - SwimRun"
    )


def test_event_name_repli_meta_description():
    html = (
        '<html><head><meta name="description" '
        'content="Résultats Spay\'cific Races 2025 - SwimRun"></head><body></body></html>'
    )
    assert chronoplace._event_name(html, "spaycific-races-2025") == (
        "Spay'cific Races 2025 - SwimRun"
    )


def test_event_name_repli_slug():
    assert chronoplace._event_name("<html><body></body></html>", "spaycific-races-2025") == (
        "Spaycific Races 2025"
    )


def test_list_epreuves_donne_les_onglets_de_levenement():
    assert chronoplace._list_epreuves(EPREUVE_494, "spaycific-races-2025") == ["494", "566"]
    assert chronoplace._list_epreuves(EPREUVE_493, "24h-vtt-de-cergy-2025") == ["492", "493"]


def test_list_epreuves_ignore_les_autres_evenements():
    html = """
    <a href="/classement/spaycific-races-2025/epreuve/494">A</a>
    <a href="/classement/un-autre-evenement-2025/epreuve/777">B</a>
    <a href="/classement/spaycific-races-2025">C</a>
    """
    assert chronoplace._list_epreuves(html, "spaycific-races-2025") == ["494"]


def test_event_type_par_epreuve():
    """Le type se déduit du nom d'épreuve, pas de celui de l'événement : le swimrun
    de Spay'cific vit dans un événement typé « Triathlon » côté chronoplace."""
    analytics_tri = chronoplace._parse_snapshot(EPREUVE_494)["analyticsContext"]
    analytics_swimrun = chronoplace._parse_snapshot(EPREUVE_566)["analyticsContext"]

    assert chronoplace._event_type(analytics_tri, "") == "triathlon-s"
    assert analytics_swimrun["event_type"] == "Triathlon"
    assert chronoplace._event_type(analytics_swimrun, "") == "swimrun"


def test_event_type_repli_sur_le_contexte_puis_le_nom():
    assert chronoplace._event_type({"event_type": "Duathlon"}, "") == "duathlon"
    assert chronoplace._event_type({}, "Aquathlon de Spay") == "aquathlon"


@pytest.mark.parametrize(
    "categorie, attendu",
    [
        ("Relais Mixte", True),
        ("Duo Masculin", True),
        ("Équipe entreprise", True),
        ("Solo Homme", False),
        ("", False),
    ],
)
def test_is_relay_category(categorie, attendu):
    assert chronoplace._is_relay_category(categorie) is attendu
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v -k "event_name or list_epreuves or event_type or relay_category"
```

Attendu : FAIL, `module ... has no attribute '_event_name'`.

- [ ] **Step 3 : Écrire l'implémentation**

Dans `backend/app/scrapers/chronoplace.py`, ajouter l'import du classifieur au-dessus de l'import de `.utils` :

```python
from .classify import classify_event_type
```

Ajouter les constantes sous `_TIME_RE` :

```python
# Marqueurs d'une participation en équipe dans la colonne `categorie`
# (« Relais Mixte », « Duo Masculin »…), comparés sans accents ni casse.
_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
_RELAY_HINTS = ("relais", "duo", "equipe")
```

Ajouter à la fin du module :

```python
def _event_name(html: str, slug: str) -> str:
    """Nom de la Course : « <événement> - <épreuve> », depuis le `<h1>`.

    Le nom de l'épreuve **doit** y figurer, sinon deux épreuves d'un même
    événement partageant date et type fusionneraient (`uq_course_identity`).
    Replis : meta `description` privée de son préfixe « Résultats », puis slug.
    """
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if h1:
        text = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)).strip()
        if text:
            return text
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return re.sub(r"^Résultats\s+", "", meta["content"].strip())
    return slug.replace("-", " ").title()


def _list_epreuves(html: str, slug: str) -> list[str]:
    """Ids des épreuves sœurs, lus dans les onglets de la page (ordre du document).

    Filtre sur le slug de l'événement courant : un lien vers un autre événement
    n'a rien à faire dans l'import.
    """
    pattern = re.compile(rf"^/classement/{re.escape(slug)}/epreuve/(\d+)/?$")
    ids: list[str] = []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        m = pattern.match(a["href"].strip())
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def _event_type(analytics: dict, event_name: str) -> str:
    """Type d'épreuve, classé sur le **nom d'épreuve**.

    `analyticsContext.event_type` décrit l'**événement**, pas l'épreuve : celui de
    Spay'cific est typé « Triathlon » alors qu'il porte aussi un swimrun. Il ne
    sert donc que de repli.
    """
    label = analytics.get("epreuve_name") or analytics.get("event_type") or event_name
    return classify_event_type(label)


def _is_relay_category(category: str) -> bool:
    """Vrai si la catégorie désigne une équipe (« Relais Mixte », « Duo Masculin »)."""
    normalized = (category or "").strip().lower().translate(_ACCENTS)
    return any(hint in normalized for hint in _RELAY_HINTS)
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py -v
uv run ruff check app/scrapers/chronoplace.py tests/test_chronoplace.py
```

Attendu : 33 tests PASS, ruff OK.

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/chronoplace.py tests/test_chronoplace.py
git commit -m "feat(scrapers): chronoplace — nom, type et épreuves sœurs (#57)"
```

---

## Task 4 : Date de l'événement via l'annuaire `/recherche`

La page de classement ne porte **aucune** date (ni `<time>`, ni meta, ni JSON-LD). L'annuaire la donne : `GET /recherche?module=classement&annee=<année>&categorie=<id>` liste les événements sous forme de cartes portant chacune un `<time datetime="2025-09-21 00:00:00">` et un lien vers le classement. Le filtre de catégorie ramène le résultat à une seule page — pas de pagination à gérer.

La date est un **bonus** : catégorie inconnue, slug introuvable ou annuaire en erreur donnent `None`, jamais un échec d'import.

**Files:**
- Modify: `backend/app/scrapers/chronoplace.py`
- Create: `backend/tests/fixtures/chronoplace_recherche_2025.html`
- Test: `backend/tests/test_chronoplace.py`

**Interfaces:**
- Consumes : Task 1 à 3.
- Produces :
  - `_fetch(client: httpx.Client, path: str) -> str` — GET sur `BASE_URL + path` ; **404 → `ValueError`** au message explicite ; autre erreur HTTP → `raise_for_status()`.
  - `_parse_event_date(html: str, slug: str) -> date | None`.
  - `_fetch_event_date(client, slug: str, year: str, category_label: str) -> date | None`.
  - `_CATEGORY_IDS: dict[str, int]` — libellé de catégorie en minuscules → id numérique.

- [ ] **Step 1 : Créer la fixture `chronoplace_recherche_2025.html`**

Créer `backend/tests/fixtures/chronoplace_recherche_2025.html` (3 cartes réelles de `/recherche?module=classement&annee=2025&categorie=12`, allégées de leurs images et icônes) :

```html
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Résultats</title></head>
<body>
  <div class="grid">
    <article class="group">
      <div class="flex flex-1 flex-col p-6">
        <h3>Le Trophée Madiot Crédit Mutuel</h3>
        <div class="mt-4 space-y-2.5">
          <div class="flex items-center text-sm text-gray-500">
            <time datetime="2026-07-19 00:00:00">19 juillet 2026</time>
          </div>
        </div>
        <div class="mt-auto pt-6">
          <a href="/classement/le-trophee-madiot-credit-mutuel-2026/epreuve/721">Voir le classement</a>
        </div>
      </div>
    </article>
    <article class="group">
      <div class="flex flex-1 flex-col p-6">
        <h3>SITRANS Bike &amp; Run de Lèves</h3>
        <div class="mt-4 space-y-2.5">
          <div class="flex items-center text-sm text-gray-500">
            <time datetime="2025-12-14 00:00:00">14 décembre 2025</time>
          </div>
        </div>
        <div class="mt-auto pt-6">
          <a href="/classement/sitrans-bike-run-de-leves-2025/epreuve/559">Voir le classement</a>
        </div>
      </div>
    </article>
    <article class="group">
      <div class="flex flex-1 flex-col p-6">
        <h3>Spay&#x27;cific Races</h3>
        <div class="mt-4 space-y-2.5">
          <div class="flex items-center text-sm text-gray-500">
            <time datetime="2025-09-21 00:00:00">21 septembre 2025</time>
          </div>
        </div>
        <div class="mt-auto pt-6">
          <a href="/classement/spaycific-races-2025/epreuve/494">Voir le classement</a>
        </div>
      </div>
    </article>
  </div>
</body>
</html>
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Ajouter en haut de `backend/tests/test_chronoplace.py`, sous les autres constantes de fixtures :

```python
RECHERCHE_2025 = _fixture("chronoplace_recherche_2025.html")  # annuaire, porteur des dates
```

Et ajouter en haut du fichier, sous `import pytest` :

```python
import httpx
```

Ajouter à la fin du fichier :

```python
class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les fixtures et enregistre les URLs demandées."""

    def __init__(self, pages: dict[str, str] | None = None, defaut: FakeResponse | None = None):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>404</html>", 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for motif, page in self.pages.items():
            if motif in url:
                return page if isinstance(page, FakeResponse) else FakeResponse(page)
        return self.defaut


def test_fetch_renvoie_le_html():
    client = FakeClient({"/classement/": EPREUVE_494})
    assert chronoplace._fetch(client, "/classement/x/epreuve/1") == EPREUVE_494
    assert client.calls == ["https://www.chronoplace.fr/classement/x/epreuve/1"]


def test_fetch_404_leve_une_erreur_explicite():
    """Le site exige la paire slug + id exacte : un slug obsolète renvoie 404."""
    client = FakeClient()
    with pytest.raises(ValueError, match="slug obsolète ou épreuve retirée"):
        chronoplace._fetch(client, "/classement/spay-swimrun-2025/epreuve/566")


def test_fetch_erreur_serveur_remonte():
    client = FakeClient(defaut=FakeResponse("", 500))
    with pytest.raises(httpx.HTTPError):
        chronoplace._fetch(client, "/classement/x/epreuve/1")


def test_parse_event_date_depuis_la_carte_de_levenement():
    from datetime import date

    assert chronoplace._parse_event_date(RECHERCHE_2025, "spaycific-races-2025") == date(2025, 9, 21)
    assert chronoplace._parse_event_date(RECHERCHE_2025, "sitrans-bike-run-de-leves-2025") == (
        date(2025, 12, 14)
    )


def test_parse_event_date_slug_absent():
    assert chronoplace._parse_event_date(RECHERCHE_2025, "un-evenement-inconnu-2025") is None


def test_parse_event_date_repli_texte_francais():
    """Si l'attribut `datetime` manque ou est illisible, on parse le texte affiché."""
    from datetime import date

    html = """
    <article><div>
      <time datetime="">21 septembre 2025</time>
      <a href="/classement/spaycific-races-2025/epreuve/494">Voir</a>
    </div></article>
    """
    assert chronoplace._parse_event_date(html, "spaycific-races-2025") == date(2025, 9, 21)


def test_fetch_event_date_interroge_lannuaire_filtre():
    from datetime import date

    client = FakeClient({"/recherche": RECHERCHE_2025})
    resultat = chronoplace._fetch_event_date(client, "spaycific-races-2025", "2025", "Triathlon")

    assert resultat == date(2025, 9, 21)
    assert client.calls == [
        "https://www.chronoplace.fr/recherche?module=classement&annee=2025&categorie=12"
    ]


def test_fetch_event_date_categorie_inconnue_ne_requete_pas():
    """La date est un bonus : une catégorie hors table ne coûte pas une requête."""
    client = FakeClient({"/recherche": RECHERCHE_2025})
    assert chronoplace._fetch_event_date(client, "x-2025", "2025", "Pétanque") is None
    assert client.calls == []


def test_fetch_event_date_annuaire_en_erreur():
    client = FakeClient(defaut=FakeResponse("", 500))
    assert chronoplace._fetch_event_date(client, "x-2025", "2025", "Triathlon") is None
```

- [ ] **Step 3 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v -k "fetch or event_date"
```

Attendu : FAIL, `module ... has no attribute '_fetch'`.

- [ ] **Step 4 : Écrire l'implémentation**

Dans `backend/app/scrapers/chronoplace.py`, compléter les imports :

```python
from datetime import date
```

sous `import re`, puis

```python
import httpx
```

au-dessus de `from bs4 import BeautifulSoup`, et enfin ajouter `parse_fr_date` à l'import de `.utils` :

```python
from .utils import normalize_time, parse_fr_date
```

Ajouter la table des catégories sous `_RELAY_HINTS` :

```python
# Ids de catégorie de l'annuaire /recherche, relevés dans le `<select name="categorie">`
# de /classements. Table statique : 17 entrées, changement improbable, et la date
# n'est qu'un bonus (catégorie inconnue → pas de recherche, pas de date).
_CATEGORY_IDS = {
    "caisse à savon": 10, "canicross": 14, "course à pied": 2,
    "courses de tracteurs tondeuses": 19, "cyclisme": 4, "cyclo-cross": 3,
    "duathlon": 18, "fauteuils roulants": 17, "gravel": 13, "hyrox": 16,
    "moto cross": 11, "multiple": 9, "trail": 1, "triathlon": 12,
    "voiture à pédales": 15, "vtt": 5, "xco": 7,
}
```

Ajouter à la fin du module :

```python
def _fetch(client: httpx.Client, path: str) -> str:
    """GET sur le site. 404 → `ValueError` explicite (le site exige slug + id exacts)."""
    response = client.get(f"{BASE_URL}{path}")
    if response.status_code == 404:
        raise ValueError(
            f"Épreuve chronoplace introuvable ({path}) : slug obsolète ou épreuve retirée."
        )
    response.raise_for_status()
    return response.text


def _parse_event_date(html: str, slug: str) -> date | None:
    """Date lue sur la carte de l'annuaire qui pointe vers ce slug.

    La carte porte `<time datetime="2025-09-21 00:00:00">21 septembre 2025</time>`
    dans un ancêtre du lien : on remonte les parents jusqu'à le trouver. Repli sur
    le texte français si l'attribut manque.
    """
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        if f"/classement/{slug}/" not in a["href"]:
            continue
        node = a
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            time_el = node.find("time")
            if not time_el:
                continue
            try:
                return date.fromisoformat((time_el.get("datetime") or "")[:10])
            except ValueError:
                return parse_fr_date(time_el.get_text(" ", strip=True))
    return None


def _fetch_event_date(client: httpx.Client, slug: str, year: str, category_label: str) -> date | None:
    """Date de l'événement via l'annuaire filtré (1 requête). `None` en cas de doute.

    La page de classement ne porte aucune date. Filtrer par année + catégorie
    ramène l'annuaire à une seule page, donc pas de pagination à parcourir.
    """
    category_id = _CATEGORY_IDS.get((category_label or "").strip().lower())
    if not category_id or not year:
        logger.info("Date non cherchée pour %s (catégorie %r inconnue)", slug, category_label)
        return None
    try:
        html = _fetch(client, f"/recherche?module=classement&annee={year}&categorie={category_id}")
    except (ValueError, httpx.HTTPError) as exc:
        logger.warning("Annuaire /recherche indisponible pour %s : %s", slug, exc)
        return None
    return _parse_event_date(html, slug)
```

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py -v
uv run ruff check app/scrapers/chronoplace.py tests/test_chronoplace.py
```

Attendu : 42 tests PASS, ruff OK.

- [ ] **Step 6 : Commit**

```bash
git add app/scrapers/chronoplace.py tests/test_chronoplace.py tests/fixtures/chronoplace_recherche_2025.html
git commit -m "feat(scrapers): chronoplace récupère la date via l'annuaire (#57)"
```

---

## Task 5 : Ligne de classement → `ScrapedResult`

**Files:**
- Modify: `backend/app/scrapers/chronoplace.py`
- Test: `backend/tests/test_chronoplace.py`

**Interfaces:**
- Consumes : Task 1 à 4.
- Produces :
  - `_build_result(row: dict, *, url: str, event_name: str, event_type: str, event_date, is_team: bool) -> ScrapedResult` — tous les paramètres après `row` sont **keyword-only**.
  - `_epreuve_results(html: str, url: str, slug: str, event_date) -> list[ScrapedResult]` — fonction **pure** (aucune requête) : HTML d'une page de classement → participants.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_chronoplace.py` :

```python
def _resultats(html: str, slug: str, event_date=None):
    return chronoplace._epreuve_results(html, "https://exemple/url-demandee", slug, event_date)


def test_epreuve_results_triathlon():
    from datetime import date

    resultats = _resultats(EPREUVE_494, "spaycific-races-2025", date(2025, 9, 21))

    assert len(resultats) == 3
    tcn = resultats[1]
    assert tcn.provider == "chronoplace"
    assert tcn.source_url == "https://exemple/url-demandee"
    assert (tcn.athlete_name, tcn.athlete_firstname) == ("MASHAYEKHI", "Sherwin")
    assert tcn.bib_number == "49"
    assert tcn.club == "TRIATHLON CLUB NANTAIS"
    assert tcn.gender == "M"
    assert tcn.rank_overall == 8
    assert tcn.total_time == "01:06:55"
    assert tcn.event_name == "Spay'cific Races 2025 - Spay'cific Triathlon S"
    assert tcn.event_type == "triathlon-s"
    assert tcn.event_date == date(2025, 9, 21)
    assert tcn.is_relay is False


def test_epreuve_results_splits_dans_les_slots_positionnels():
    """Les 5 slots triathlon sont ré-étiquetés par sport dans services/mapping."""
    premier = _resultats(EPREUVE_494, "spaycific-races-2025")[0]

    assert premier.swim_time == "00:10:53"
    assert premier.t1_time == "00:00:48"
    assert premier.bike_time == "00:31:01"
    assert premier.t2_time == "00:00:52"
    assert premier.run_time == "00:04:33"


def test_epreuve_results_splits_absents_rendus_en_tiret():
    """Ligne réelle : splits non chronométrés (« — »), temps total présent."""
    sans_splits = _resultats(EPREUVE_494, "spaycific-races-2025")[2]

    assert sans_splits.total_time == "01:30:44"
    assert (sans_splits.swim_time, sans_splits.bike_time, sans_splits.run_time) == ("", "", "")


def test_epreuve_results_le_scraper_ne_se_prononce_pas_sur_le_statut():
    """Aucun label DNF/DNS/DSQ observé : on laisse mapping.derive_status décider."""
    assert all(r.status == "" for r in _resultats(EPREUVE_494, "spaycific-races-2025"))


def test_epreuve_results_relais_detecte_par_la_categorie():
    resultats = _resultats(EPREUVE_566, "spaycific-races-2025")

    assert [r.is_relay for r in resultats] == [False, True, True]
    assert resultats[1].category == "Relais Mixte"
    assert resultats[0].event_type == "swimrun"


def test_epreuve_results_nom_dequipe_limite_connue():
    """`split_athlete_name` coupe un nom d'équipe au premier jeton non capitalisé.

    Comportement hérité de TimePulse, verrouillé ici volontairement : on reste
    cohérent avec les autres providers plutôt que d'inventer une règle locale.
    """
    relais = _resultats(EPREUVE_566, "spaycific-races-2025")[1]

    assert relais.athlete_name == "MENARDAIS FERDINAND"
    assert relais.athlete_firstname == "/ COMPAIN LENA"


def test_epreuve_results_is_team_du_snapshot():
    """24 h VTT : `isTeam:true`, aucune colonne catégorie — le relais vient du snapshot."""
    resultats = _resultats(EPREUVE_493, "24h-vtt-de-cergy-2025")

    assert all(r.is_relay for r in resultats)
    assert resultats[0].athlete_name == "CREPHAISSON"
    assert resultats[0].category == ""
    assert resultats[0].gender == ""


def test_epreuve_results_duree_superieure_a_24h():
    assert _resultats(EPREUVE_493, "24h-vtt-de-cergy-2025")[1].total_time == "24:00:13"


def test_epreuve_results_raw_data_conserve_toutes_les_cellules():
    """`nb_tours` et `ecart` ne sont ni temps ni split : ils ne vivent que là."""
    relais = _resultats(EPREUVE_566, "spaycific-races-2025")[1]

    assert relais.raw_data["nb_tours"] == "15"
    assert relais.raw_data["ecart"] == "+5:16"
    assert relais.raw_data["temps"] == "02:05:37"


def test_build_result_sans_colonne_dossard():
    """Certaines épreuves n'affichent pas le dossard : pas de KeyError, champ vide."""
    resultat = chronoplace._build_result(
        {"position": "1", "nom": "ONICOACH", "temps": "05:54:28"},
        url="u", event_name="E", event_type="triathlon", event_date=None, is_team=True,
    )

    assert resultat.bib_number == ""
    assert resultat.club == ""
    assert resultat.rank_overall == 1
    assert resultat.is_relay is True
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v -k "epreuve_results or build_result"
```

Attendu : FAIL, `module ... has no attribute '_epreuve_results'`.

- [ ] **Step 3 : Écrire l'implémentation**

Dans `backend/app/scrapers/chronoplace.py`, ajouter l'import du modèle et des helpers :

```python
from .base import ScrapedResult
```

au-dessus de `from .classify import ...`, et compléter l'import de `.utils` :

```python
from .utils import normalize_rank, normalize_time, parse_fr_date, split_athlete_name
```

Ajouter la table des splits sous `_CATEGORY_IDS` :

```python
# Colonne source → slot positionnel de ScrapedResult. Les slots portent des noms
# triathlon par convention ; services/mapping.build_splits les ré-étiquette selon
# `event_type` (duathlon → course1/course2, swimrun → swim/run…).
_SPLIT_FIELDS = {
    "T_natation": "swim_time",
    "T1": "t1_time",
    "T_velo": "bike_time",
    "T2": "t2_time",
    "T_course_a_pied": "run_time",
}
```

Ajouter à la fin du module :

```python
def _build_result(
    row: dict[str, str],
    *,
    url: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    is_team: bool,
) -> ScrapedResult:
    """Une ligne de classement → un participant.

    `status` reste vide : aucun label DNF/DNS/DSQ n'a été observé sur les épreuves
    sondées, et `services/mapping.derive_status` applique alors son heuristique.
    """
    surname, firstname = split_athlete_name(row.get("nom", ""))
    category = (row.get("categorie") or "").strip()

    result = ScrapedResult(source_url=url, provider="chronoplace")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.athlete_name = surname
    result.athlete_firstname = firstname
    result.bib_number = (row.get("dossard") or "").strip()
    result.club = (row.get("club") or "").strip()
    result.category = category
    result.gender = (row.get("genre") or "").strip()
    result.rank_overall = normalize_rank(row.get("position"))
    result.rank_gender = normalize_rank(row.get("clasmt_genre"))
    result.total_time = _time_or_empty(row.get("temps", ""))
    for column, field in _SPLIT_FIELDS.items():
        setattr(result, field, _time_or_empty(row.get(column, "")))
    result.is_relay = bool(is_team) or _is_relay_category(category)
    # Tout le brut est conservé : `nb_tours` et `ecart` ne vivent que là.
    result.raw_data = dict(row)
    return result


def _epreuve_results(
    html: str, url: str, slug: str, event_date: date | None
) -> list[ScrapedResult]:
    """HTML d'une page de classement → participants. Pur : aucune requête."""
    snapshot = _parse_snapshot(html)
    analytics = snapshot.get("analyticsContext") or {}
    event_name = _event_name(html, slug)
    event_type = _event_type(analytics, event_name)
    is_team = bool(snapshot.get("isTeam"))
    return [
        _build_result(
            row,
            url=url,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            is_team=is_team,
        )
        for row in _parse_table(html)
    ]
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py -v
uv run ruff check app/scrapers/chronoplace.py tests/test_chronoplace.py
```

Attendu : 52 tests PASS, ruff OK.

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/chronoplace.py tests/test_chronoplace.py
git commit -m "feat(scrapers): chronoplace mappe une ligne vers ScrapedResult (#57)"
```

---

## Task 6 : Orchestration `scrape_event_all`

Une URL pointe une épreuve, mais la page liste ses sœurs (onglets). On les importe **toutes** : le modèle l'autorise (une `source_url` porte N `Course`, comme les heats Breizh Chrono) et un seul lien du Sheet couvre alors l'événement complet — triathlon **et** swimrun pour Spay'cific Races.

Deux pièges vérifiés sur la source :
- une URL sans `/epreuve/<id>` est redirigée vers la première épreuve, mais **la redirection perd la query string** : `?perPage=all` serait ignoré et on ne lirait que 50 lignes. D'où `_resolve_epreuve_id`, une requête de plus, uniquement dans ce cas ;
- une épreuve sœur en échec ne doit pas emporter l'import de l'épreuve demandée : on journalise et on continue. L'échec de l'épreuve **demandée**, lui, remonte.

**Files:**
- Modify: `backend/app/scrapers/chronoplace.py`
- Test: `backend/tests/test_chronoplace.py`

**Interfaces:**
- Consumes : Task 1 à 5.
- Produces :
  - `_resolve_epreuve_id(client: httpx.Client, slug: str) -> str`.
  - `scrape_event_all(url: str) -> list[ScrapedResult]` — point d'entrée public, signature attendue par `ScraperProtocol`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_chronoplace.py` :

```python
URL_494 = "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494"

# L'ordre compte : « /classement/spaycific-races-2025 » est aussi un préfixe des URLs
# d'épreuve, il doit donc rester en dernier (FakeClient prend le premier motif qui matche).
PAGES_SPAYCIFIC = {
    "/epreuve/494": EPREUVE_494,
    "/epreuve/566": EPREUVE_566,
    "/recherche": RECHERCHE_2025,
    "/classement/spaycific-races-2025": EPREUVE_494,  # forme sans /epreuve/<id>
}


def _client_factice(monkeypatch, pages=None, defaut=None):
    client = FakeClient(pages if pages is not None else dict(PAGES_SPAYCIFIC), defaut)
    monkeypatch.setattr(chronoplace.httpx, "Client", lambda *a, **k: client)
    return client


def test_scrape_event_all_importe_toutes_les_epreuves_de_levenement(monkeypatch):
    """Un seul lien du Sheet couvre le triathlon ET le swimrun de Spay'cific."""
    client = _client_factice(monkeypatch)

    resultats = chronoplace.scrape_event_all(URL_494)

    assert len(resultats) == 6  # 3 lignes de fixture par épreuve
    assert {r.event_type for r in resultats} == {"triathlon-s", "swimrun"}
    assert client.calls == [
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494?perPage=all",
        "https://www.chronoplace.fr/recherche?module=classement&annee=2025&categorie=12",
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/566?perPage=all",
    ]


def test_scrape_event_all_date_cherchee_une_seule_fois(monkeypatch):
    """La date est celle de l'événement : une requête d'annuaire, pas une par épreuve."""
    from datetime import date

    client = _client_factice(monkeypatch)

    resultats = chronoplace.scrape_event_all(URL_494)

    assert len([c for c in client.calls if "/recherche" in c]) == 1
    assert all(r.event_date == date(2025, 9, 21) for r in resultats)


def test_scrape_event_all_source_url_est_lurl_demandee(monkeypatch):
    """`source_url` sert de clé de cache TTL : toutes les Course partagent celle du Sheet."""
    _client_factice(monkeypatch)

    resultats = chronoplace.scrape_event_all(URL_494)

    assert {r.source_url for r in resultats} == {URL_494}


def test_scrape_event_all_url_sans_epreuve_resout_lid_dabord(monkeypatch):
    """La redirection du site perd la query string : `?perPage=all` serait ignoré."""
    client = _client_factice(monkeypatch)

    resultats = chronoplace.scrape_event_all(
        "https://www.chronoplace.fr/classement/spaycific-races-2025"
    )

    assert len(resultats) == 6
    assert client.calls[0] == "https://www.chronoplace.fr/classement/spaycific-races-2025"
    assert client.calls[1] == (
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494?perPage=all"
    )


def test_scrape_event_all_slug_obsolete_leve(monkeypatch):
    """Lien mort du Sheet (`spay-swimrun-2025`) : erreur explicite, pas de silence."""
    _client_factice(monkeypatch, pages={})

    with pytest.raises(ValueError, match="slug obsolète ou épreuve retirée"):
        chronoplace.scrape_event_all(
            "https://www.chronoplace.fr/classement/spay-swimrun-2025/epreuve/566"
        )


def test_scrape_event_all_epreuve_soeur_en_echec_est_ignoree(monkeypatch):
    """Une sœur qui tombe ne doit pas emporter l'épreuve demandée."""
    pages = dict(PAGES_SPAYCIFIC)
    pages["/epreuve/566"] = FakeResponse("", 500)
    _client_factice(monkeypatch, pages=pages)

    resultats = chronoplace.scrape_event_all(URL_494)

    assert len(resultats) == 3
    assert {r.event_type for r in resultats} == {"triathlon-s"}


def test_resolve_epreuve_id_sans_composant(monkeypatch):
    client = FakeClient({"/classement/": "<html><body>vide</body></html>"})

    with pytest.raises(ValueError, match="Aucune épreuve"):
        chronoplace._resolve_epreuve_id(client, "spaycific-races-2025")
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v -k "scrape_event_all or resolve_epreuve_id"
```

Attendu : FAIL, `module ... has no attribute 'scrape_event_all'`.

- [ ] **Step 3 : Écrire l'implémentation**

Ajouter à la fin de `backend/app/scrapers/chronoplace.py` :

```python
def _resolve_epreuve_id(client: httpx.Client, slug: str) -> str:
    """Id de la première épreuve d'un événement, pour une URL sans `/epreuve/<id>`.

    Le site redirige bien `/classement/<slug>` vers cette épreuve, mais la
    redirection **perd la query string** : suivre le 302 avec `?perPage=all`
    rendrait les 50 premières lignes seulement. On résout donc l'id d'abord.
    """
    html = _fetch(client, f"/classement/{slug}")
    epreuve_id = str(_parse_snapshot(html).get("epreuveId") or "")
    if not epreuve_id:
        raise ValueError(f"Aucune épreuve trouvée pour l'événement chronoplace « {slug} ».")
    return epreuve_id


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de **toutes** les épreuves de l'événement.

    Une URL pointe une épreuve, mais la page liste ses sœurs (onglets) : on les
    importe toutes, comme les heats Breizh Chrono. Coût : une requête par épreuve.
    """
    slug, epreuve_id = _parse_url(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if not epreuve_id:
            epreuve_id = _resolve_epreuve_id(client, slug)
        html = _fetch(client, _epreuve_path(slug, epreuve_id))

        # La date vaut pour l'événement entier : une seule requête d'annuaire.
        analytics = _parse_snapshot(html).get("analyticsContext") or {}
        event_date = _fetch_event_date(
            client, slug, analytics.get("event_year", ""), analytics.get("event_type", "")
        )

        results = _epreuve_results(html, url, slug, event_date)
        done = {epreuve_id}
        for sibling in _list_epreuves(html, slug):
            if sibling in done:
                continue
            done.add(sibling)
            try:
                page = _fetch(client, _epreuve_path(slug, sibling))
            except (ValueError, httpx.HTTPError) as exc:
                # Une sœur en échec ne doit pas emporter l'épreuve demandée.
                logger.warning("Épreuve sœur %s ignorée : %s", sibling, exc)
                continue
            results.extend(_epreuve_results(page, url, slug, event_date))
    return results
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py -v
uv run ruff check app/scrapers/chronoplace.py tests/test_chronoplace.py
```

Attendu : 59 tests PASS, ruff OK.

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/chronoplace.py tests/test_chronoplace.py
git commit -m "feat(scrapers): chronoplace importe toutes les épreuves de l'événement (#57)"
```

---

## Task 7 : Enregistrement dans le registre, intégration et documentation

**Files:**
- Modify: `backend/app/scrapers/registry.py`
- Modify: `backend/tests/test_chronoplace.py`
- Modify: `backend/tests/test_integration_scrapers.py`
- Modify: `AGENTS.md` (racine du dépôt)

**Interfaces:**
- Consumes : `chronoplace.scrape_event_all(url)` de la Task 6.
- Produces : `ChronoplaceProvider` (attribut `name = "chronoplace"`), visible dans `registry.provider_names()` et routé par `registry.detect_provider`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_chronoplace.py` :

```python
def test_registry_detecte_le_provider():
    from app.scrapers import registry

    assert registry.detect_provider(URL_494) == "chronoplace"
    assert registry.detect_provider("https://chronoplace.fr/classement/x/epreuve/1") == (
        "chronoplace"
    )


def test_registry_expose_chronoplace_comme_ciblable():
    """`provider_names()` alimente la validation de `--provider` en CLI."""
    from app.scrapers import registry

    assert "chronoplace" in registry.provider_names()


def test_registry_nattrape_pas_les_autres_hosts():
    from app.scrapers import registry

    assert registry.detect_provider("https://www.klikego.com/resultats/x/1") != "chronoplace"
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_chronoplace.py -v -k registry
```

Attendu : FAIL — `detect_provider` renvoie `playwright` (le fallback) au lieu de `chronoplace`.

- [ ] **Step 3 : Écrire l'implémentation**

Dans `backend/app/scrapers/registry.py`, ajouter `chronoplace` à l'import du haut de fichier (ordre alphabétique, avant `klikego`) :

```python
from app.scrapers import (
    breizhchrono,
    chronoplace,
    klikego,
    prolivesport,
    sportinnovation,
    timepulse,
    wiclax,
)
```

Ajouter la classe juste avant `class PlaywrightProvider:` :

```python
class ChronoplaceProvider:
    name = "chronoplace"

    def matches(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        return host == "chronoplace.fr" or host.endswith(".chronoplace.fr")

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return chronoplace.scrape_event_all(url)
```

Ajouter l'instance à la fin de `PROVIDERS` (le host est disjoint des autres, la position est libre) :

```python
PROVIDERS: list[ScraperProtocol] = [
    BreizhChronoProvider(),
    WiclaxProvider(),
    KlikegoProvider(),
    TimePulseProvider(),
    ProLiveSportProvider(),
    SportInnovationProvider(),
    ChronoplaceProvider(),
]
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

```bash
uv run pytest tests/test_chronoplace.py tests/test_registry.py -v
```

Attendu : 62 tests PASS dans `test_chronoplace.py`, `test_registry.py` toujours vert.

- [ ] **Step 5 : Ajouter les tests d'intégration (réseau réel)**

Dans `backend/tests/test_integration_scrapers.py`, ajouter l'entrée au dictionnaire `LIVE_URLS` :

```python
    "chronoplace": "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494",
```

Puis ajouter à la fin du fichier :

```python
@pytest.mark.integration
def test_chronoplace_importe_les_epreuves_soeurs():
    """Un seul lien couvre le triathlon et le swimrun de Spay'cific Races 2025."""
    results = registry.scrape_event_all(LIVE_URLS["chronoplace"])

    assert len(results) > 200, "le classement complet (perPage=all) n'a pas été rendu"
    assert {"triathlon-s", "swimrun"} <= {r.event_type for r in results}
    assert any(r.event_date == date(2025, 9, 21) for r in results)
    # Splits triathlon peuplés, et le TCN est bien présent.
    tri = [r for r in results if r.event_type == "triathlon-s"]
    assert any(r.swim_time and r.bike_time and r.run_time for r in tri)
    assert any("TRIATHLON CLUB NANTAIS" in (r.club or "") for r in tri)


@pytest.mark.integration
def test_chronoplace_slug_obsolete_leve():
    """Lien mort du Sheet : le site exige la paire slug + id exacte."""
    with pytest.raises(ValueError, match="slug obsolète ou épreuve retirée"):
        registry.scrape_event_all(
            "https://www.chronoplace.fr/classement/spay-swimrun-2025/epreuve/566"
        )
```

- [ ] **Step 6 : Lancer les tests d'intégration**

```bash
uv run pytest -m integration -k chronoplace -v
```

Attendu : 4 tests PASS (détection, import générique, épreuves sœurs, lien mort). Ces tests touchent le réseau réel : en cas d'échec, vérifier d'abord que `https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494` répond bien.

- [ ] **Step 7 : Mettre à jour la documentation**

Dans `AGENTS.md`, section « Fournisseurs supportés », remplacer la première ligne :

```markdown
Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète).
```

par :

```markdown
Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live, ProLiveSport, Sportinnovation,
Chronoplace (individuel + épreuve complète). Chronoplace (Laravel + Livewire) se
lit en `GET ?perPage=all` — pas de POST Livewire — et importe **toutes** les
épreuves de l'événement pointé par l'URL.
```

- [ ] **Step 8 : Vérifier la suite complète**

```bash
uv run pytest -m "not integration"
uv run ruff check .
```

Attendu : toute la suite verte (≈ 570 tests), ruff « All checks passed! ». Ne rien annoncer comme terminé avant d'avoir vu ces deux sorties.

- [ ] **Step 9 : Commit**

```bash
git add app/scrapers/registry.py tests/test_chronoplace.py tests/test_integration_scrapers.py ../AGENTS.md
git commit -m "feat(scrapers): enregistre chronoplace dans le registre (#57)"
```

---

## Vérification finale

Une fois les 7 tâches faites :

```bash
# depuis backend/
uv run pytest -m "not integration"      # suite unitaire complète
uv run pytest -m integration -k chronoplace   # réseau réel
uv run ruff check .

# import de bout en bout sur une base de dev, via la CLI
uv run python -m app.cli rescrape-db \
  --url https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494
```

Le bilan doit annoncer 1 épreuve ciblée, 0 en erreur, et un nombre de participants ajoutés > 200 (219 triathlètes + 41 swimrunners au moment du sondage).
