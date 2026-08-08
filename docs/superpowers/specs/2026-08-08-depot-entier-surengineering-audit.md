# Audit sur-ingénierie — dépôt entier (2026-08-08)

> Troisième passage, **à froid sur l'arbre complet** : racine, `.github/`,
> `Taskfile.yml`, `backend/scripts/`, `docs/`, `specs/`, `.specify/`, plus le
> code arrivé de `main` (#239) — c'est-à-dire tout ce que les deux relevés du
> 2026-08-06 ne couvraient pas, eux qui s'arrêtaient à `backend/app` et
> `frontend/`. Branche `ponytail-analyse`.
>
> Périmètre : sur-ingénierie et complexité seulement. Ni bugs, ni sécurité, ni
> performance — ces axes relèvent d'une revue normale.
>
> **11 findings : 5 traités, 6 écartés.** L'intérêt de ce document est surtout
> dans les 6 refus : ce sont eux qu'on rejugerait au prochain passage.
>
> Les deux relevés précédents :
> [`2026-08-06-backend-surengineering-audit.md`](2026-08-06-backend-surengineering-audit.md),
> [`2026-08-06-frontend-surengineering-audit.md`](2026-08-06-frontend-surengineering-audit.md).

## Comment lire

Mêmes étiquettes que les deux relevés précédents :

| Étiquette | Sens |
|---|---|
| `delete` | code mort, souplesse jamais utilisée, fonctionnalité spéculative. Remplacement : rien. |
| `stdlib` | réimplémentation de ce que la bibliothèque standard livre déjà. |
| `native` | dépendance ou code faisant ce que la plateforme fait déjà. |
| `yagni` | abstraction à une seule implémentation, config que personne ne règle, couche à un seul appelant. |
| `shrink` | même logique, moins de lignes. |

## Récapitulatif

| # | Étiquette | Objet | Volume | État |
|---|---|---|---:|---|
| 1 | `delete` | `docs/superpowers/plans/` — 37 plans exécutés | −37 926 l. | ❌ écarté |
| 2 | `yagni` | seconde chaîne SDD : `specs/` + `.specify/` | −25 562 l. | ❌ écarté |
| 3 | `delete` | `backend/scripts/repair_courses.py` | −206 l. | ❌ écarté |
| 4 | `yagni` | `Taskfile.yml`, 22 alias d'une ligne | −173 l. | ⚠️ partiel |
| 5 | `delete` | `audit_scrapers.py`, table d'URLs figée | −158 l. | ✅ requalifié |
| 6 | `yagni` | squelette fan-out ×4 dans `registry.py` | −90 l. | ✅ traité |
| 7 | `shrink` | 12 dicts `HEADERS`, même User-Agent | −60 l. | ✅ traité |
| 8 | `shrink` | 4 `FanoutTrace` identiques | −60 l. | ✅ traité |
| 9 | `native` | `zod` + `react-hook-form` + `@hookform` | −3 deps | ❌ écarté |
| 10 | `yagni` | `docker-compose.yml` + tâches `docker:*` | −40 l. | ✅ traité |
| 11 | `yagni` | `services/course_review.py` | −22 l. | ❌ écarté |

**Appliqué : ≈ −190 lignes de code, −1 fichier de configuration.** Le gros du
volume relevé (63 480 lignes d'artefacts de processus) a été délibérément
conservé — voir « Ce qui a été écarté, et pourquoi ».

---

## Ce qui a été traité

### 5. `delete` → requalifié — la table d'URLs d'`audit_scrapers.py`

`backend/scripts/audit_scrapers.py` (158 l.) tape sur les vrais sites via le
registre, une URL d'épreuve par fournisseur, et rend un rapport Markdown : OK/KO,
participants, champs peuplés, type détecté.

Son `FIXTURE_URLS` était un **sous-ensemble strict** du `LIVE_URLS` de
`tests/test_integration_scrapers.py` — les six premières entrées identiques au
caractère près, et **rien au-delà**. Le registre est passé à 14 fournisseurs, la
copie du script est restée à 6 : `chronoplace`, `chronoweb`, `competitor`,
`oktime`, `raceresult`, `runnerbreizh`, `sporthive` et `t2area` n'étaient jamais
audités, et le rapport ne le disait pas.

**La suppression n'était pas la bonne coupe.** Le script mesure ce que les tests
n'assertent pas : taux de champs peuplés, présence de splits et de rangs. Le
défaut était la table figée, pas le script. Il importe désormais `LIVE_URLS` —
une seule table pour le dépôt, 6 → 14 fournisseurs, et pas de désynchronisation
possible au prochain ajout.

C'est la troisième occurrence du motif de #76 dans ce dépôt : une définition
recopiée, dont une copie se fige et ment par omission.

### 6 + 8. `yagni` + `shrink` — le fan-out avait un contrat sans domicile

Deux findings distincts qui s'appellent, appliqués ensemble.

**8 — quatre `FanoutTrace` identiques.** `klikego`, `wiclax`, `chronoplace` et
`chronoweb` déclaraient chacun la même dataclass à cinq champs, avec une
docstring disant « même contrat que la trace Klikego ». Pendant ce temps
`oktime`, `sporthive` et `raceresult` importaient celle de klikego, et
`import_service` s'annotait `registry.klikego.FanoutTrace`. Le contrat était
partagé par sept modules et **hébergé chez un fournisseur**. Il vit maintenant
dans `scrapers/base.py`.

**6 — le squelette fan-out recopié quatre fois.** `RaceResult`, `OkTime`,
`Sporthive` et `Wiclax` répétaient le même `__init__`, la même bascule
`single_heat` avec sa trace synthétique 1-heat, le même
`try/except/append/raise` et le même appel à `scrape_event_fanout`. Une base
`FanoutProvider` le porte ; chaque provider ne déclare plus que son `_module`,
et `_echec_slug_est_url` pour RaceResult dont la sous-unité est désignée par
l'URL.

**Trois providers gardent leur méthode, et c'est le point** : `Klikego` parse
l'URL et passe quatre arguments au moteur, `ChronoWeb` a un `single_heat` qui ne
lève pas, `Chronoplace` n'en accepte pas. Ils héritent pour l'`__init__`, pas
pour le comportement. Les docstrings par provider sont conservées mot pour mot.

**Le vrai gain n'est pas les 131 lignes.** `_FANOUT_PROVIDERS`, tuple de sept
classes tenu à la main pour deux `isinstance`, disparaît au profit
d'`isinstance(provider, FanoutProvider)`. Un huitième provider à fan-out ne peut
plus être oublié dedans — le type le dit.

### 7. `shrink` — un seul User-Agent

Douze modules de `app/scrapers/` déclaraient leur `HEADERS` ; **onze y
répétaient le même User-Agent au caractère près** (le relevé en comptait neuf :
`timepulse` et `sporthive` le nomment `_HEADERS`, le balayage cherchait
`HEADERS = {`. Les deux ont été convergés à la relecture du 2026-08-08). `utils.DEFAULT_HEADERS` le
porte ; les modules qui n'avaient que lui l'importent tel quel, ceux qui ajoutent
un `Referer`, un `Accept` ou un `access-token` composent `{**DEFAULT_HEADERS, …}`.

**Trois User-Agent divergent réellement et n'ont pas été convergés** :
`chronoweb` et `runnerbreizh` sont en `Chrome/120.0`, `competitor` en
`Chrome/124.0.0.0`. C'est très probablement du copier-coller plus ancien, mais un
User-Agent est une valeur **mesurée contre un vrai site** et rien ne le vérifie
sans réseau. Chacun porte un marqueur `ponytail:` nommant l'écart et sa condition
de levée — `pytest -m integration` vert sur le fournisseur.

Bilan honnête : −36 lignes de `HEADERS`, +12 pour la constante, +12 pour les
marqueurs, soit **≈ +10 lignes nettes**. Le gain n'est pas là : changer
l'User-Agent est passé de onze éditions à une, et les trois écarts sont écrits au
lieu d'être subis.

### 10. `yagni` — `docker-compose.yml`

Troisième façon de lancer la pile en local, à côté des lanceurs de dev
multi-worktree qui sont la vraie boucle. Le déploiement, lui, est **Render en
`runtime: python`** (pas via Dockerfile) et **Vercel en build natif** (pas de
`vercel.json`). Retiré avec les deux tâches `docker:*` du Taskfile et les
mentions du README.

**Les deux `Dockerfile` restent** : ils sont l'échappatoire d'un déploiement
auto-hébergé, et plusieurs commentaires du code s'y réfèrent comme à la référence
de production (`--host 0.0.0.0`).

Relevé au passage et **hors périmètre** : le compose montait
`db_data:/app/triathlon.db`, un volume nommé sur un chemin de **fichier** —
Docker y crée un répertoire, SQLite n'aurait pas pu ouvrir la base. La pile ne
démarrait probablement pas telle quelle, ce qui explique sans doute qu'elle n'ait
manqué à personne.

### 4. `yagni` → partiel — la description périmée du Taskfile

Le Taskfile est conservé (voir plus bas), mais sa tâche `b:dev` annonçait encore
« premier port libre à partir de 8001 » — faux depuis le passage au port
éphémère du même lot de travaux. Corrigée.

C'est l'illustration du coût que le finding nommait : une troisième copie des
mêmes commandes est une troisième copie à tenir à jour, et c'est celle qu'on
oublie.

---

## Ce qui a été écarté, et pourquoi

**C'est la partie utile de ce document.** Ces six lignes ont été instruites et
refusées ; les rejuger coûterait le même travail pour le même résultat.

### 1. Les 37 plans SDD de `docs/superpowers/plans/` — **conservés**

37 926 lignes, 37 fichiers, ~1 025 lignes de moyenne. C'est le plus gros artefact
du dépôt, devant `backend/app` (23 347 l.). Ce sont des transcriptions
d'exécution pas-à-pas, avec blocs de code, pour des features livrées — et le code
qu'elles contiennent est mesurablement faux : après application des deux premiers
audits, 6 plans citent encore `_detect_event_type`, 3 citent
`PlaywrightProvider`, 2 citent `ScrapeForm`, 1 cite `setup_tracing` — et deux
features de `specs/` citent `ScrapeForm` de leur côté. Tous supprimés.

**Décision : garder.** La valeur historique l'emporte sur le coût de portage, et
`AGENTS.md` ne les désigne pas comme jetables. Conséquence assumée : ces
documents ne sont **pas** une source fiable sur l'état du code — seule
`docs/superpowers/specs/` l'est, et encore, pour les sondages et audits.

### 2. La seconde chaîne SDD (`specs/` + `.specify/`) — **conservée**

`specs/` (13 features, 20 153 l.) et `.specify/` (templates et scripts Spec Kit,
5 409 l.) forment un second outillage de spécification complet, parallèle à
Superpowers, pour une application de 23 347 lignes.

**Décision : garder — et ce n'est pas un oubli.** `AGENTS.md` en fait la règle
d'or : « deux voies complètes et parallèles, jamais croisées », et « le choix de
la voie appartient à l'utilisateur ». Le coût est réel et connu ; il est accepté.

### 3. `backend/scripts/repair_courses.py` — **conservé**

206 lignes, écrites le 2026-07-17, **zéro référence** hors du fichier lui-même :
ni README, ni Taskfile, ni CI, ni docs. Réparation one-shot de deux dégâts
« hérités d'imports antérieurs aux correctifs des scrapers » — noms dérivés du
slug d'URL, dates absentes chez Wiclax/TimePulse.

**Décision : garder.** Le script est idempotent, donc son passage ne laisse
aucune trace en base : on ne peut pas prouver qu'il a été exécuté en production,
seulement qu'aucun automatisme ne le lance. Le supprimer sur cette base serait un
pari.

### 4. `Taskfile.yml` — **conservé** (seule sa description périmée est corrigée)

173 lignes, 22 tâches, chacune un alias d'une ligne pour un `uv run` ou
`npm run` déjà écrit dans `README.md` **et** dans `AGENTS.md` — troisième copie
des mêmes commandes, au prix d'installer `go-task`.

**Décision : garder.** Le confort d'un lanceur unique vaut la troisième copie.
Coût accepté : c'est elle qui vieillit, comme l'a montré `b:dev`.

### 9. `zod` + `react-hook-form` + `@hookform/resolvers` — **conservés**

Trois dépendances de **production** (11 Mo dans `node_modules`) pour **un seul**
formulaire, `components/scrape/ManualResultForm.tsx`, la saisie manuelle de
secours quand aucun scraper ne reconnaît l'URL. Son schéma de 18 lignes dit
exactement : quatre champs requis, treize optionnels avec `""` par défaut.
Aucun test dédié.

Le remplacement natif était identifié : `required` sur les champs obligatoires et
`FormData` à la soumission. Il aurait même **amélioré l'accessibilité** —
l'implémentation actuelle affiche l'erreur dans un `<span>` non relié au champ
(ni `aria-describedby`, ni `aria-invalid`), là où la validation de contrainte du
navigateur l'est par construction et déplace le focus sur le premier champ
fautif.

**Décision : garder.** La pile servira au prochain formulaire complexe.

### 11. `services/course_review.py` — **conservé**

22 lignes pour une fonction de trois (`course.reliability_override = verdict ;
db.flush() ; return course`), avec un seul appelant en production, `admin.py:90`.

**Décision : garder**, et c'était le finding le plus faible du lot. L'archi en
couches d'`AGENTS.md` prescrit `api → services → repositories → DB` et des
« routers fins » ; inliner l'affectation ferait d'`admin.py` le seul endroit du
dépôt où une route écrit un attribut de modèle. La docstring porte en outre le
pourquoi de FR-039 — lever l'avis humain fait réapparaître le *dernier* verdict
calculé, pas celui qui valait à la décision.

---

## Vérifié et écarté

Deux pistes examinées qui n'en sont pas, notées pour ne pas les re-signaler :

- **`frontend/lib/roles.ts`** (43 l., un hook, deux appelants) semble être une
  couche mince. Sa docstring porte la raison d'être : deux écrans posent la même
  question — attribuer un rôle, choisir celui qu'une adresse donnera à
  l'inscription — et le service y répond par le même 403. Deux copies
  divergeraient dans le sens le plus dangereux, celui qui propose ce qui sera
  refusé.
- **Les modules de `lib/utils/` à un seul export** (`event.ts`, `raceOrder.ts`,
  `url.ts`, `time.ts`…) : tous ont de nombreux appelants, et le répertoire
  compte douze modules mono-sujet. Ils suivent la convention plutôt qu'ils ne
  l'enfreignent — déjà tranché comme finding n° 12 de l'audit frontend.

## Ce que l'audit n'a **pas** trouvé à couper

- **`.github/workflows/`** (609 l., 4 workflows) — `ci.yml` est mince (deux jobs
  symétriques), `batch.yml` est long (248 l.) mais chaque étape porte une
  mesure : ouverture et fermeture du pare-feu Azure, verrou de concurrence,
  résumé, artefact.
- **`frontend/scripts/backend-url.mjs`** (116 l.) — déjà épargné par l'audit
  frontend, et la raison tient : chaque garde répond à un bug mesuré.
- **`backend/tests/`** (34 501 l.) — le volume dépasse `app/`, ce qui est normal
  pour un dépôt dont les fournisseurs sont des cibles mouvantes. Aucun motif de
  duplication mécanique relevé au-delà de celui du finding n° 5.

## Suite

Tout ce qui devait l'être est appliqué. Deux choses restent ouvertes et ne sont
pas des coupes :

1. **Les trois User-Agent divergents** (`chronoweb`, `runnerbreizh`,
   `competitor`) portent un marqueur `ponytail:`. Ils se convergent le jour où
   `pytest -m integration` passe au vert sur ces fournisseurs, pas avant.
2. **Les artefacts de processus vieillissent en silence** — 63 480 lignes
   conservées, dont on a mesuré qu'une partie cite du code supprimé. Ce n'est pas
   une coupe à faire, c'est une propriété à connaître : ne jamais lire un plan de
   `docs/superpowers/plans/` comme une description de l'état du code.

**Relecture du 2026-08-08** (`requesting-code-review`, trois relecteurs sur des
périmètres disjoints) : aucun point critique. Trois écarts d'application relevés
et corrigés dans la foulée — les deux `_HEADERS` du n° 7 ci-dessus ; trois
providers (`oktime`, `sporthive`, `raceresult`) qui importaient encore
`FanoutTrace` **chez klikego** alors que le n° 6+8 lui avait donné un domicile
dans `base.py` ; et l'absence de tout lien vérifié entre le `name` d'une entrée
`PROVIDERS` et le module auquel elle délègue — depuis que la paire est une
donnée et non deux écritures, un croisement passerait toute la suite unitaire
(`test_chaque_provider_delegue_au_module_de_son_nom` le referme).
