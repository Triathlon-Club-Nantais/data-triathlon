# Moteur RaceResult générique — design

> Issue #50 (sous-issue de #33, section B, point n°3 de l'ordre d'attaque).
> Analyse fondée sur un sondage réel de l'API RaceResult le 2026-07-18 :
> épreuves `311052`, `383352`, `383809`, `393893`, `399938`, `406844`.

## Objectif

Un moteur unique couvrant trois façades d'un même produit :

| Host | Nature |
|---|---|
| `my*.raceresult.com` | RaceResult direct |
| `espace-competition.com` | front RaceResult (`new RRPublish(el, <eventId>, …)`) |
| `chronoconsult.fr` | façade WordPress au-dessus de RaceResult |

Aucun Playwright : tout passe par l'API JSON publique.

## Ce que le sondage a établi

### Le chaînage d'appels

1. `GET /{eventId}/RRPublish/data/config?page=results`
   → `key`, `contests` (id → nom), `lists`, `splits`, `eventname`, `server`.
2. `GET /{eventId}/RRPublish/data/list?key=…&listname=…&page=results&contest=N&r=all`
   → **redirige en 301** vers `/{eventId}/results/list`. `follow_redirects=True`
   est obligatoire, sinon réponse vide.

### La date d'épreuve n'est pas dans l'API

Ni `config` ni `list` ne portent de date. Elle est dans le **JSON-LD schema.org**
de la page `/{eventId}/results` :

```json
{"@type":"Event","name":"Triathlon de Roanne Villerest","startDate":"2026-06-18",
 "location":{"address":{"addressLocality":"SAINT-HERBLAIN"}}}
```

C'est la seule source de `event_date`, et elle donne aussi la ville.

### L'algorithme de mapping des colonnes

Extrait de `RRPublish.js` (donc autoritatif, pas une heuristique) :

```js
i = {DataFields[e]: e};  Fields[e].DataCol = i[Fields[e].Expression]
```

L'index de colonne d'un champ vaut `DataFields.index(Field.Expression)`.
`DataFields` préfixe toujours `BIB` et `ID`, qui n'ont pas d'entrée dans `Fields`.

### Trois pièges non mentionnés dans l'issue

**a) `contest=0` n'est pas universel.** Sur `393893` (Rumilly), `contest=0` renvoie
404 sur toutes les listes ; il faut interroger contest par contest (1…4), chacun
livrant son propre payload. Sur `383352` (Grenoble), certaines listes veulent
`contest=0`, d'autres leur `Contest` propre. Le couple (liste, contest) doit être
résolu **empiriquement**.

**b) Certaines listes annoncées en config répondent 404 en dur.** `399938`
(Roanne) n'expose qu'une liste `En ligne|Final`, en 404 sur les 9 valeurs de
contest. L'épreuve est inexploitable malgré un config valide.

**c) Le groupement des lignes porte le statut.** `data` est un dict imbriqué à
deux niveaux :

```
data["#1_Distance M"]["#1_"]              → finishers
data["#1_Distance M"]["#2_Abandons"]      → DNF
data["#1_Distance M"]["#3_Non Partants"]  → DNS
```

Le groupe de niveau 1 identifie le **contest**, celui de niveau 2 le **statut**.
La cellule de rang vaut en outre littéralement `"DNF"` / `"DNS"`.

### Ce qu'une épreuve triathlon sort réellement

`393893` contest 4 (Distance M, 308 finishers, 6 DNF, 33 DNS) :

```json
DataFields: ["BIB","ID","OuStatut([ClassementGénéral.P])","DossardBis",
  "AfficherNom","SexeMF","#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]",
  "ucase([CLUB])","[Natation.OVERALL.P]","[Natation]","[Transition1.OVERALL.P]",
  "[Transition1]","[Vélo.OVERALL.P]","[Vélo]","[Transition2.OVERALL.P]",
  "[Transition2]","[Course.OVERALL.P] ","[Course]","TIME",
  "Arrivée.OVERALL.GapTop"]
Labels: ["Pl.","#","Nom","M|F","Cat.","Club","","Nat.","","T1","","Vélo","",
  "T2","","CAP","Temps",""]
Ligne:  ["79","56","2.","79","Alexis ROUX","M","1.S4M","GRESIVAUDAN TRIATHLON",
  "2.","20:04","3.","00:53","2.","1:05:49","45.","00:56","3.","34:14",
  "2:01:56","+2:44"]
```

Club, catégorie, sexe et les cinq segments triathlon sont présents. Les noms sont
en `Prénom NOM` — l'inverse de la convention `NOM Prénom` de Wiclax/TimePulse.

## Décisions

| Question | Décision |
|---|---|
| Choix des listes | Balayer toutes les listes exploitables et **fusionner** |
| Surface d'API | `scrape_event_all()` seul — pas de `scrape()` athlète-unique |
| Épreuve sans liste exploitable | `ValueError` explicite |

Le `scrape()` réclamé par l'issue est un reliquat de rédaction : le projet a
supprimé la voie athlète-unique, et `ScraperProtocol` (`registry.py:32-44`)
n'expose plus que `matches()` + `scrape_event_all()`.

## Architecture

Un module `app/scrapers/raceresult.py` — fonctions, pas classe, calqué sur
`wiclax.py` — plus un `RaceResultProvider` dans `registry.py`. Aucune autre
couche n'est touchée : `provider_names()` est dérivé de `PROVIDERS`, et les
consommateurs (`sheet_source`, `bulk_import_service`, `cli/validators`,
`api/v1/scrape`) suivent automatiquement.

### Routage

```python
class RaceResultProvider:
    name = "raceresult"
    _HOSTS = ("raceresult.com", "espace-competition.com", "chronoconsult.fr")
```

Test `host == h or host.endswith(f".{h}")` — celui de Wiclax, qui écarte les
hosts sosies. Détection explicite par host, jamais par sniffing de contenu : un
nouveau front RaceResult = une ligne dans `_HOSTS`.

### Résolution de l'`eventId`

| Forme d'URL | Extraction |
|---|---|
| `my*.raceresult.com/399938/…` | segment numérique du path — zéro requête |
| `espace-competition.com/index.php?…comp_uid=3178` | 1 GET → `new RRPublish(el, 406844, …)` |
| `chronoconsult.fr/result/<slug>/` | idem |

`comp_uid` est **ignoré** : ce n'est pas la clé de données, l'`eventId`
RaceResult l'est. Le regex doit tolérer les espaces autour de l'argument
(`RRPublish(document.getElementById("divRRPublish"),  399938 , 'results'…)`),
avec repli sur `my*.raceresult.com/(\d+)/api/logo`, présent sur les mêmes pages.
Échec des deux motifs → `ValueError` citant l'URL.

### Pipeline

Un seul `httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)` ouvert
dans `scrape_event_all` et passé aux helpers — pattern `sportinnovation.py`, qui
rend l'ensemble injectable en test sans réseau.

1. `_resolve_event_id(url, client) -> str`
2. `_fetch_meta(event_id, client)` → JSON-LD de `/{id}/results` →
   `(event_name, event_date, ville)`
3. `_fetch_config(event_id, client)` → `key`, `contests`, `lists`, `splits`
4. `_iter_payloads(...)` → pour chaque liste : essayer `contest = list["Contest"]`
   si non nul et non `"0"`, sinon `"0"` puis chaque contest déclaré ; s'arrêter au
   premier succès **par liste**. Un 404 est journalisé en `debug` et n'interrompt
   rien. Borne réseau : `len(lists) + len(contests)` requêtes au pire, ~5 en
   pratique.
5. Fusion : dédoublonnage par `(contest, dossard)`, en retenant pour chaque clé la
   ligne au plus grand nombre de champs non vides. Une liste « Individuel » et une
   liste « Relais » se complètent au lieu de s'écraser.
6. Aucun payload exploitable → `ValueError` citant l'`eventId` et les listes
   essayées. Le batch la collecte en `BatchFailure(url, label, message)` et
   l'affiche sous « Épreuves en erreur (détail) ».

### Granularité des courses

Une `Course` par **contest**, via le nom qualifié
`"Triathlon de Rumilly - Distance M"`, comme `_qualify_event_name` chez Wiclax.
C'est ce qui évite les collisions de dossards de l'issue #21 : Rumilly porte un
dossard `1245` en Distance XS et un `280` en Distance M. Le nom de contest vient
de la clé de groupe de niveau 1 (`#1_Distance M`), avec repli sur
`config["contests"][id]`.

## Mapping des colonnes

**Étage 1 — l'index.** `col = DataFields.index(Field.Expression)`. `BIB` étant
toujours `DataFields[0]`, le dossard ne passe par aucune heuristique.

**Étage 2 — le rôle sémantique.** Normaliser conjointement `Field.Label` et
`Field.Expression` (minuscule, sans accents, en pelant les enrobages `ucase(…)`,
`OuStatut(…)`, `if(…;X;…)`, `[…]`, `#`, `"…" &`), puis scorer contre une table de
motifs :

| Champ | Expressions observées |
|---|---|
| nom | `AfficherNom`, `if([CONTEST]=3;[NomRelais]…;[AfficherNom])`, `NomEquipe`, `NomRelais` |
| club | `ucase([CLUB])`, `ClubOuVille` |
| catégorie | `AGEGROUP.NAMESHORT`, `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]` |
| sexe | `SexeMF`, `SEX` |
| temps total | `TIME`, `TempsTotal`, `TempsCorrigé`, `Finish`, `Arrivée` |
| rang général | `ClassementGénéral.P` |

Deux règles de sûreté tirées du terrain :

- toute expression suffixée `.P` / `.OVERALL.P` est un **rang**, jamais un temps —
  sinon `[Natation.OVERALL.P]` (`"2."`) serait pris pour le temps de natation, qui
  est dans la colonne suivante ;
- `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]` colle rang et catégorie
  (`"1.S4M"`) → `_split_rank_category` en tire `rank_category=1` et
  `category="S4M"`.

Un `_clean_cell` retire les décorations d'affichage : `[img:https://…]`, le `#`
de `"#" & [BIB]`, le point final des rangs.

Un champ non reconnu n'est pas perdu : il part dans `raw_data`.

## Splits

Remplir la liste ordonnée `segments: list[tuple[str, str]]` de `ScrapedResult`,
pas les cinq slots positionnels. Rumilly sort `Nat. / T1 / Vélo / T2 / CAP`, mais
le Swimrunman `311052` sort neuf splits et l'Ekiden `383809` quatre relais :
`segments` prime sur les slots et lève le plafond de 5, ce qui règle au passage la
limite « swimrun multi-legs collapsé » documentée dans `AGENTS.md`.

Le libellé d'un segment vient de `Field.Label`, avec repli sur le `Label` du split
correspondant dans `config["splits"]`. Les colonnes de rang de split
(suffixe `.P`) sont exclues.

## Statut

Deux signaux concordants, tous deux passés à `utils.derive_status_from_label`,
le groupe primant sur la cellule :

- nom du groupe de niveau 2 : `#2_Abandons` → DNF, `#3_Non Partants` → DNS ;
- cellule de rang : `"DNF"`, `"DNS"`.

Puis le nettoyage systématique de la maison (`wiclax.py:133-139`) : statut
non-finisher → `total_time` vidé et les trois rangs à `None`.

`event_type` est délégué à `classify.classify_event_type` sur le nom qualifié,
sans aucune logique locale.

## Correctif ciblé dans `utils.split_athlete_name`

RaceResult sort `Prénom NOM`. Le repli actuel prend le dernier token comme nom,
donc `"Jean DE LA TOUR"` donne nom = `"TOUR"`. Ajout : si les derniers tokens sont
en majuscules, les prendre tous. Corrige RaceResult et tout provider à même
convention ; couvert par `tests/test_scrapers_utils.py`.

## Tests

Fixtures JSON et HTML réduites à la main dans `tests/fixtures/`, provenance et
date de récupération en docstring comme le fait `test_wiclax.py` :

| Fixture | Rôle |
|---|---|
| `raceresult_config_rumilly.json` | config avec plusieurs listes et contests |
| `raceresult_list_rumilly_m.json` | liste tronquée à ~5 lignes : finisher + DNF + DNS |
| `raceresult_page_meta.html` | page `/results` réduite au seul JSON-LD |
| `chronoconsult_result_page.html` | page façade pour la résolution d'`eventId` |

`_fetch_config` / `_fetch_list` / `_fetch_meta` monkeypatchés (pattern
`test_wiclax.py`), ou faux client httpx quand c'est la résolution d'URL qui est
sous test (pattern `test_sportinnovation.py`).

Cas de non-régression qui comptent :

- mapping par `DataFields.index(Expression)`, pas par position ;
- rejet des colonnes de rang suffixées `.P` ;
- résolution empirique du contest : 404 sur `contest=0` puis succès sur `contest=1` ;
- liste morte de Roanne → `ValueError` messagé ;
- `Prénom NOM` correctement scindé, y compris nom composé ;
- DNF/DNS déduits du groupe, avec temps et rangs purgés ;
- routage des trois hosts dans le registry, et host sosie non capté.

Enfin une entrée `raceresult` dans `LIVE_URLS` de `test_integration_scrapers.py`,
que les deux tests paramétrés prendront automatiquement.

## Hors périmètre

- Pas de `scrape()` athlète-unique (voie supprimée du projet).
- Pas de Playwright, y compris en repli : la page RRPublish est un SPA alimenté
  par la même API, un repli ne récupérerait rien de plus.
- Les autres providers de la section B de #33 (fftri.t2area, ok-time, sporthive,
  competitor…) restent dans leurs propres sous-issues.
