# Phase 0 — Research : runnerbreizh.fr

La recherche exploratoire a été faite avant le cadrage, sur le site réel :
`docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md` (7 épreuves,
19 requêtes, 27/07/2026). Ce document ne répète pas les mesures — il consigne les
**décisions** qu'elles ont permis de prendre, et ce qui a été écarté.

Aucun `NEEDS CLARIFICATION` ne subsiste dans le Technical Context.

---

## D1 — Client HTTP et parsing : httpx + BeautifulSoup, pas Playwright

**Decision** : `httpx.Client` synchrone + BeautifulSoup (parser `lxml`), comme les
providers HTML existants.

**Rationale** : le site est du HTML statique servi par Apache/PHP 7.4. Les 19
requêtes du sondage ont toutes répondu en 200 avec le classement complet dans le
document, sans exécution de JavaScript, sans session : les trois cookies posés
(`PHPSESSID`, `urlsiterunners56`, `analitycs-runners56-ok`) ne conditionnent rien.

**Alternatives considérées** :

- **Playwright** (le fallback du registre) — rejeté : coût d'un navigateur pour
  une page statique, et le fallback ne sait de toute façon pas produire de
  résultats exploitables (`scrape_event_all` y lève).
- **Parsing par expressions régulières** — rejeté : le markup porte des attributs
  de style volumineux et variables (couleur selon le genre, fond selon la
  parité de ligne). BeautifulSoup rend le parsing indifférent à ce bruit.

---

## D2 — Canonicalisation de l'URL par allowlist, pas par soustraction

**Decision** : reconstruire la query avec le seul paramètre `CourseFichierGpsNom`
et repartir de la page 1.

**Rationale** : 8 des 10 liens du Sheet portent `&page=2` ou `&page=3`, et
certains `&tricourse=&Sexe=`. `Sexe=F` renvoie un sous-ensemble : conserver le
paramètre amputerait l'import. Une allowlist reste juste si le site ajoute un
quatrième paramètre de vue ; une soustraction (`del params["page"]`) ne le
serait pas.

**Portée exacte, vérifiée en base** : la canonicalisation garantit l'import
complet et le `source_url` des `ScrapedResult`, mais **pas** la clé de cache TTL.
`import_service.import_event` passe l'URL reçue telle quelle comme `event_url`, et
c'est elle que `mapping.get_or_create_course` stocke dans `Course.source_url` ; le
cache se cherche ensuite par égalité stricte sur cette colonne
(`get_latest_by_source_url`). Mesuré sur les deux graphies Quiberon du Sheet :
**1 course, 322 participations, aucun doublon** — la seconde graphie re-scrape
(7 requêtes) puis constate 322 « déjà en base ». Faire converger la clé de cache
demanderait de canonicaliser dans `import_service`, donc un point d'extension par
provider : hors périmètre de #56, à ouvrir en suiveur si le coût des re-scrapes
devient sensible.

**Alternatives considérées** :

- **Prendre l'URL telle quelle et paginer en avant** — rejeté : les pages 1..N-1
  seraient perdues, c'est-à-dire les meilleurs classés, et silencieusement.
- **Normaliser dans `sheet_source`** — rejeté : la query distingue légitimement
  deux heats Breizh Chrono. La connaissance de ce qui est une « vue » chez
  runnerbreizh appartient au provider runnerbreizh.

---

## D3 — Arrêt de pagination sur page sans ligne, jamais sur le total annoncé

**Decision** : boucler jusqu'à la première page dont `table.tableau-courses` n'a
aucune ligne de données, avec un plafond de sécurité journalisé.

**Rationale** : mesuré sur `page=9` et `page=20` de Plouescat et `page=8` de
Quiberon — le site répond 200 avec 2 `<tr>` (bandeau + en-tête) et rien d'autre.
Le total de la colonne « Classement » (`1/356`) est tentant comme borne, mais il
compte des **équipes** en relais : « TriBreizh en Duo » annonce `/31` pour 62
lignes sur 2 pages. Une borne `ceil(31/50)=1` s'arrêterait au milieu de l'épreuve.

**Alternatives considérées** :

- **Lire le dernier lien de pagination** (`…&page=8`) — rejeté : le bloc de
  pagination est stylé et tronqué (`1 2 3 4 … 8`), sa structure est plus fragile
  que le critère « la table est vide ».
- **Borne par le total annoncé** — rejeté, faux en relais (mesuré).

---

## D4 — Métadonnées de l'épreuve depuis le `<title>`

**Decision** : parser le `<title>` (`Résultats de la course du 19/07/2026 -
<nom> - <ville> - <km>KM - Type : <discipline>`), retirer du nom le suffixe de
distances entre parenthèses, alimenter `distance_km` avec le kilométrage.

**Rationale** : c'est le seul porteur de la date en format français ; le bandeau
HTML la rend en anglais abrégé (`19 Jul 2026`). Le retrait des parenthèses est
mesuré : `geocode_service.extract_city` rend `"Plouescat"` sur le nom nettoyé
contre `"Plouescat S (0.75/20/5)"` sur le nom intégral — soit 4 épreuves du panel
géocodables au lieu de 0. `classify.extract_distance_km` ne trouve rien dans un
nom sans « km », d'où le renseignement explicite de `distance_km`.

**Alternatives considérées** :

- **Parser le bandeau `#titre-courses`** — rejeté : date en anglais, et
  l'information y est éclatée entre plusieurs `<span>` stylés.
- **Garder le nom intégral** — rejeté en clarification (perte du géocodage,
  risque de doublon d'épreuve avec un autre fournisseur).
- **Se fier au `Type :` du titre pour la discipline** — rejeté comme source
  primaire : il ne porte pas la taille (S/M/L). `classify_event_type(nom)` la
  déduit et couvre déjà les trois disciplines observées ; le `Type :` ne sert que
  de repli.

---

## D5 — Splits par position + discipline, pas par libellé de colonne

**Decision** : colonnes 2/3/5 → `swim_time` / `bike_time` / `run_time` des slots
positionnels de `ScrapedResult` ; `services.mapping.build_splits` ré-étiquette
selon `event_type`.

**Rationale** : les libellés d'en-tête sont **identiques quelle que soit la
discipline** (mesuré sur 7 épreuves) et mentent : en duathlon « 1ère épreuve » est
une course à pied, en aquathlon la colonne « Vélo » reste affichée mais vide. Le
gabarit `_SPLIT_KEYS_BY_SPORT` existant produit déjà `course1`/`bike`/`course2`
pour un duathlon et `swim`/`run` pour un aquathlon : le travail est fait, à
condition de remplir les slots et non des libellés.

**Alternatives considérées** :

- **Lire les colonnes par libellé d'en-tête** (l'approche T2Area) — rejeté : ici
  les libellés sont trompeurs, c'est exactement le piège.
- **Utiliser `ScrapedResult.segments`** (chemin déplafonné, étiquettes libres) —
  rejeté : le site publie au plus 3 segments, et `segments` obligerait à écrire
  les libellés métier en dur dans le scraper alors que `build_splits` les connaît.

---

## D6 — Genre depuis le suffixe de catégorie

**Decision** : dernier caractère de la catégorie (`S3M` → `M`, `MAF` → `F`).

**Rationale** : disponible sur **toutes** les lignes, y compris les anonymes
(`0 /M`). L'alternative — la classe du lien coureur (`<a class="M">`) — n'existe
que pour les inscrits au site : 16 lignes sur 50 à Quiberon. Deux sources
partielles à réconcilier pour la même information est un coût sans gain.

---

## D7 — Aucune modification de l'infrastructure d'import

**Decision** : ne toucher ni `import_service`, ni `quality.py`, ni `mapping.py`.

**Rationale** :

- **Sans dossard** : la déduplication de repli par athlète (multiset) existe déjà
  et est générique, motivée par les 5 599 participations sans bib de
  Sportinnovation (commit `b49e295`). `bib_number=""` suffit.
- **Sans club** : `athlete_repository.resolve` ne met à jour `Athlete.club` que
  si un club est fourni — un import runnerbreizh n'efface donc rien.
- **Rangs partagés en relais** : `quality._rank_anomalies` les comptera comme
  doublons et l'épreuve sortira `is_reliable=false`. Assouplir la règle
  toucherait tous les providers, sur la foi d'une seule épreuve en duo : limite
  documentée, ticket séparé si le besoin se confirme.

---

## D8 — Lignes anonymes importées, sous leur libellé brut

**Decision** : `athlete_name = "?DOSSARD #43637"`, `athlete_firstname = ""`,
`bib_number = ""`, identifiant conservé dans `raw_data`.

**Rationale** : les écarter créerait des trous dans le classement (3 sur 322 à
Quiberon), que `quality.analyze` compte en `rank_gap` → `is_reliable=false` →
ratio de place masqué pour **tous** les participants de l'épreuve
(cf. `2026-07-25-meilleure-place-ratio-design.md`). Le libellé intégral en nom
évite par ailleurs le `('?DOSSARD', '#43637')` que rendrait
`split_athlete_name`, qui afficherait `#43637` comme un prénom.

**Alternatives considérées** :

- **Ignorer ces lignes** — rejeté (perte de fiabilité de toute l'épreuve).
- **Mettre l'identifiant en `bib_number`** — rejeté : `43637` sur une épreuve de
  322 classés n'est pas un dossard, et un faux dossard fausserait la clé
  `UNIQUE(course_id, bib_number)`.
- **Libellé neutre « Participant non identifié »** — rejeté en clarification :
  s'éloigne de la source et impose une convention à maintenir.

---

## D9 — Republication : avertissement, pas de reconstruction d'URL

**Decision** : `logger.warning` une fois par épreuve quand la mention
« Chronométrée par X » désigne un provider supporté.

**Rationale** : à l'identique de T2Area. Sur le panel, 2 épreuves sur 7 portent la
mention, et son lien pointe l'accueil du chronométreur
(`http://www.breizhchrono.com`), jamais l'épreuve : aucune URL source n'est
constructible. Seul l'opérateur peut fournir le lien natif — le journal est là
pour qu'il sache que c'est possible (Breizh Chrono publierait dossards **et**
clubs).

---

## D10 — Tests : fixtures réelles réduites, réseau derrière `integration`

**Decision** : 6 fixtures HTML réduites (extraits réels du 27/07/2026, attributs
de style élagués, structure intacte), monkeypatch de `httpx.Client` sur le modèle
de `tests/test_t2area.py` ; 1 test réseau réel marqué `integration`.

**Rationale** : principe III, non négociable. Les pages réelles pèsent 20 à 93 ko
— inutilisables telles quelles comme fixtures ; les fixtures existantes du dépôt
font 2 à 11 ko. Chaque fixture couvre un cas distinct : page pleine, dernière page
partielle, page vide, duathlon (libellés trompeurs), aquathlon (colonne vide),
duo (rangs partagés).
