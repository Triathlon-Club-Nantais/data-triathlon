# Sources multiples d'une épreuve : sources, bascule, re-scrape, fusion (epic #275)

Renvoyé depuis `backend/app/api/AGENTS.md`.

## Sources d'une épreuve : `GET /courses/{id}/sources` (#284)

**Publique**, lecture seule, et ce n'est pas un oubli de garde : la décision D4
de #275 rend la liste visible de tous — quel chronométreur alimente le classement
affiché est une information de lecture. Ce qui reste fermé, c'est l'écriture
(soumettre une URL, basculer l'active) et le **nom du soumetteur** :
`CourseSourceOut` ne porte que `id`, `url`, `provider`, `is_active`,
`last_scraped_at`, jamais `created_by`. L'ordre — active en tête, puis les
passives par `created_at` — appartient à `course_source_repository.list_for_course`
et n'est pas cosmétique : sans lui, la source affichée sauterait d'un
rechargement à l'autre. Une épreuve inconnue est un **404**
(`NotFoundError("Course introuvable")`, comme les deux routes voisines), une
épreuve sans source une **liste vide** — confondre les deux ferait lire un
identifiant inventé comme « aucune source ».

## Basculer la source active : `PATCH /admin/courses/{id}/sources/{source_id}` (#285)

Le seul geste d'administration qui **scrape** — d'où son module à part,
`admin_course_sources.py`, sa dépendance à `Settings` et sa durée en secondes.
Garde `courses:sources`, et non `courses:write` : le pouvoir voisin est borné aux
quatre champs d'identité, où corriger un libellé ne détruit rien ; ici le
classement affiché est remplacé **en entier** (décision D2 de #275, un upsert par
dossard laisserait survivre les lignes de l'ancienne source, donc exactement le
mélange de deux chronométreurs que l'epic existe pour supprimer). Rend la liste
des sources dans la forme et l'ordre de `GET /courses/{id}/sources`, pour que
l'écran se réaffiche sans second appel.

Cinq choses à ne pas défaire :

- **L'ordre des quatre étapes est le contrat** : scraper, valider, détruire,
  réimporter. Rien de destructeur n'est écrit avant qu'on tienne un classement
  utilisable — c'est ce qui rend impossible l'accident propre à cette route, une
  épreuve vidée par un geste qui échoue ensuite à la remplir. Ce n'est pas un
  choix de style : `import_event` **commite** en interne, et un `begin_nested()`
  autour ne le contient pas (mesuré sur SQLAlchemy 2.0.51 — le `commit` clôt la
  transaction *externe*). Aucun rollback n'était donc disponible ; n'avoir rien
  écrit est plus solide de toute façon.
- **Le cache TTL est neutralisé des deux côtés.** `is_fresh` court-circuiterait
  le scrape, mais `force=True` ne suffit pas : la sonde par manche à l'intérieur
  de `_scrape_all` juge chaque sous-épreuve fraîche indépendamment, et l'épreuve
  qu'on bascule est par définition la plus fraîche de la base. D'où
  `import_service.scrape_for_replacement`, qui passe `use_cache_probe=False` —
  sans quoi une épreuve fan-out perdrait toutes ses manches.
- **Un scrape qui publie une autre épreuve est refusé** (422), pas importé.
  `mapping.get_or_create_course` apparie sur `(nom, date, type, relais)` à
  l'égalité stricte : un libellé différent chez le second chronométreur créerait
  une **nouvelle** épreuve et laisserait celle qu'on vient de vider à zéro
  résultat, sans qu'aucune exception ne passe. Zéro résultat est refusé pour la
  même raison — banal sur le chemin d'import ordinaire (succès à zéro compteur),
  ici un classement effacé.
- **`is_active: false` est refusé** (400). L'index partiel autorise zéro active,
  et une épreuve sans active n'est plus scrapée (#282) ni affichée avec sa source
  (#279) : le seul moyen de changer d'active est d'en désigner une autre.
- **Bloquant, et sans progression.** #275 tranche que la bascule et le re-scrape
  à la demande « doivent partager le même mécanisme, pas en inventer deux » : le
  SSE d'administration appartient donc à #118, et aucun critère d'acceptation de
  #285 ne porte sur la progression.

La purge des fiches coureur devenues vides relève ses candidats **avant** la
suppression et ne tranche qu'**après** le réimport — même primitive et même piège
que `DELETE /admin/courses/{id}`.

## Re-scraper une épreuve à la demande : `POST /admin/courses/{id}/rescrape` (#118)

La promesse faite par la section précédente : même module SSE que
`POST /scrape/event/stream` (`scrape.py`), gardé par `courses:sources` comme la
bascule (geste voisin), mais **upsert** plutôt que remplacement total — c'est ce
qui distingue les deux gestes. Router mince
(`admin_course_rescrape.py`) → générateur de service
(`admin_actions.iter_rescrape_course`) → repositories existants ; zéro
abstraction nouvelle, tout ce qui suit est réutilisé tel quel :
`_require_same_event` (refus zéro résultat / épreuve divergente, FR-009),
`athlete_repository.only_on_course`/`delete_orphans_among` (purge d'orphelins,
même primitive que #285/#117), `admin_action_log_repository.create`.

Quatre points à ne pas défaire :

- **La garde (404/409) est synchrone, hors du générateur.** `iter_rescrape_course`
  est une **fonction ordinaire**, pas un générateur : appelée directement par la
  route, elle lève tout de suite si la course est introuvable, sans source
  active, ou déjà en cours de re-scrape — et ne rend un générateur (celui qui
  scrape et persiste) qu'une fois la garde passée. Raison : `StreamingResponse`
  (Starlette) envoie le statut HTTP **avant** de tirer le premier élément du
  générateur — une exception levée depuis l'intérieur d'un générateur déjà en
  flux ne peut plus jamais devenir un 404/409, seulement une coupure à 200.
- **Le scrape et la persistance tournent dans un thread dédié, indépendant de
  la consommation du flux SSE** (FR-011). Un générateur Python synchrone
  n'avance qu'au rythme des `next()` que lui fait `StreamingResponse` ; dès
  qu'un client se déconnecte, Starlette cesse ces appels, et tout ce qui suit
  le dernier `yield` consommé — la persistance elle-même — ne s'exécuterait
  jamais sans ce thread. Patron déjà présent pour le fan-out Klikego
  (`_scrape_all_streaming`, `queue.Queue` + sentinel), étendu ici à **toute**
  l'opération. `ponytail:` la session dédiée (`SessionLocal()`) n'est jamais
  fermée explicitement — le thread qui la possède peut survivre à la requête
  HTTP ; upgrade si le volume de re-scrapes concurrents en fait un jour un
  problème mesuré.
- **Cache TTL désarmé par heat sur le chemin streamé** — `_scrape_all_streaming`
  et `iter_import_event` gagnent `use_cache_probe: bool = True`, défaut inchangé
  pour tout appelant existant, désarmé (`False`) uniquement par l'appel admin.
  Même besoin que #285 (`scrape_for_replacement(use_cache_probe=False)`), côté
  streamé cette fois : sans lui, un re-scrape demandé sur une épreuve fan-out
  fraîchement importée sauterait tous ses heats jugés frais.
- **Le verrou de concurrence est un `dict[int, bool]` en mémoire, process
  unique** (FR-007/SC-005), acquis à l'entrée d'`iter_rescrape_course`, relâché
  en `finally`. `ponytail:` migrer vers un verrou DB si le service passe un jour
  multi-instance — cf. le docstring de `batch_runs.py` pour la même contrainte.

**Piège de test à ne pas répéter** : la route utilise une session dédiée
(`SessionLocal()`, patron `scrape_event_stream`), **pas** `Depends(get_db)` —
elle doit survivre à la requête HTTP elle-même. Cette session n'est donc **pas**
substituable par `app.dependency_overrides[get_db]` : un test qui la ferait
tourner pour de vrai frapperait la base de dev réelle, jamais celle de test
(mesuré — deux re-scrapes réels de « Triathlon de Vierzon 2026 » déclenchés par
inadvertance lors de l'écriture de cette section). `test_admin_course_rescrape.py`
mocke donc `admin_actions.iter_rescrape_course` lui-même pour n'éprouver que le
contrat HTTP/SSE, exactement comme `test_scrape_api.py` mocke
`import_service.iter_import_event` — le comportement réel (scrape, upsert,
purge, verrou) est couvert à la couche service, dans
`test_services/test_admin_actions.py`, sur `db_session`.

## Aperçu d'impact avant fusion : `GET /admin/courses/{id}/merge-impact` (#286)

`?absorbed_id={id}`, gardé par **`courses:sources`** — le pouvoir qui *arbitre*,
pas un pouvoir de lecture : même raison que `deletion-impact` sous
`courses:delete`, qui peut trancher peut mesurer. `courses:write` ne conviendrait
pas, sa description est bornée aux quatre champs d'identité. Le module est
`admin_course_merge.py`, distinct d'`admin_data.py` : la fusion appartient à
l'epic #275, pas aux quatre gestes correctifs de #117, et #287 (la fusion) s'y
ajoutera.

Quatre points à ne pas défaire :

- **Deux épreuves qui diffèrent sur `name`, `event_date` et `event_type` sont le
  cas nominal**, pas une erreur : deux chronométreurs ne nomment ni ne classent
  la même épreuve de la même façon. Les deux côtés sortent tels quels.
- **Le rapprochement se fait par dossard** (`uq_participation_bib`), et un
  dossard absent ou vide **n'a pas d'équivalent** — rien ne permet de le
  rapprocher, et le compter comme sauvé annoncerait des résultats qui
  disparaîtraient. `NOT EXISTS` corrélé et non `NOT IN` : un seul partant sans
  dossard côté cible rendrait un `NOT IN` toujours faux, donc l'aperçu
  annoncerait « aucune perte ».
- **`tcn_participations_without_match` est le chiffre qui décide** ; il sort de
  la même agrégation que le total, en une requête à deux colonnes. Le nombre de
  requêtes est constant (10 mesurées), et un test de
  `tests/test_services/test_course_merge.py` le vérifie en comparant deux
  tailles de jeu — rapprocher les classements en Python coûterait 1811 lignes
  sur la plus chargée des épreuves.
- **`same_source_url` regarde *toutes* les sources de la cible, l'active comme
  les passives** : `UNIQUE(course_id, url)` ignore `is_active`, donc une URL déjà
  connue de la cible ne peut pas y être repointée — la fusion n'ajoute alors
  aucune source, elle supprime un doublon (cas Mesquer, ids 38 et 50 en base de
  dev). `athletes_orphaned` vient de `athlete_repository.only_on_course`, la
  **même** fonction que la purge de #117 : l'annonce et l'acte de #287 ne peuvent
  pas diverger à base constante.

Fusionner une épreuve avec elle-même est un **400** (message français) : le geste
n'a rien à absorber, et #287 supprimerait la cible qu'on croit garder.

## Fusionner : `POST /admin/courses/{id}/merge` (#287)

`{"absorbed_id": <id>}`, même module que son aperçu. L'absorbée est nommée dans le
corps et la cible dans le chemin parce que la ressource s'écrit du point de vue de
ce qui **survit** : l'épreuve `{id}` garde son identité, son classement et sa
source active. Rend les mêmes chiffres que l'aperçu annonçait, plus la liste des
sources de la cible dans la forme de `GET /courses/{id}/sources` (#284).

Six choses à ne pas défaire :

- **La fusion ne re-scrape rien**, et c'est la décision qui la définit. La cible
  garde ses participations ; l'absorbée disparaît avec les siennes, et son URL la
  rejoint en **passive**. Prendre les données de l'autre chronométreur est un
  *second* geste, la bascule de #285 — deux décisions, deux gestes. Les fondre
  donnerait un geste dont personne ne pourrait prédire le classement obtenu.
- **Deux pouvoirs exigés — `courses:sources` et `courses:delete`**, par deux
  `Depends(require_permission(...))` sur la route : la fabrique nomme *un* pouvoir,
  les composer est le mécanisme, il n'en faut pas de troisième et **aucun pouvoir
  n'est ajouté au catalogue** — « fusionner » n'est pas une capacité de plus, c'est
  la conjonction de deux capacités existantes. L'arbitrage des sources ne perd
  aucune ligne (la bascule réimporte), la fusion oui : exiger le seul
  `courses:sources` donnerait une suppression d'épreuve à qui n'en a pas le droit.
- **Seule la source *active* de l'absorbée survit ; ses passives meurent avec
  elle.** Ce n'est pas une économie : c'est ce qui rend vraie la promesse de
  l'aperçu, qui annonce « aucune source ne sera ajoutée » sur le seul examen de
  l'URL active (`same_source_url`). Faire suivre les passives ferait apparaître des
  sources non annoncées et rendrait le prédicat faux. Les deux ressources appellent
  le **même** `_url_already_known`, et le refus de la fusion sur soi-même le même
  `_pair_or_400` : l'annonce et l'acte ne peuvent pas diverger à base constante.
  Une passive perdue reste rattrapable par le chemin ordinaire — la recoller recrée
  une épreuve, que #288 signale et qu'une seconde fusion rapproche.
- **La source repointée reste passive sans condition**, même si la cible n'a
  aucune active. `course_source_repository.move_to` est l'inverse d'`attach` sur ce
  point, et c'est délibéré : une passive n'est jamais scrapée (#282), ce qui est
  exactement ce qui rend la fusion non destructrice. L'activer ferait scraper l'URL
  de l'absorbée au prochain `rescrape-db`, qui recréerait l'épreuve supprimée sous
  sa propre identité.
- **Le repointage passe par la relation, et précède le `delete`.** `move_to` écrit
  `source.course = target`, seule écriture qui retire aussi la ligne de
  `absorbed.sources` : sans elle le `delete-orphan` de la collection supprimerait
  l'URL au `db.delete(absorbed)` qui suit, donc le geste censé la sauver la
  perdrait. `is_active` et `course_id` changent dans le **même** `UPDATE` — un seul
  `flush`, contrairement à `set_active` : découper ferait toucher la cible à une
  ligne encore active, contre l'index partiel `UNIQUE(course_id) WHERE is_active`.
- **L'ordre des lectures est le piège.** Résumé, URL active, compte de
  participations et candidats à la purge se relèvent **avant** la suppression :
  après, l'épreuve n'a plus ni source ni résultat, la liste des candidats revient
  vide et la purge devient un no-op qu'aucune erreur ne signale — même primitive et
  même piège que `DELETE /admin/courses/{id}`.

L'entrée de journal (`course.merge`) est rattachée à la **survivante** et porte
l'identité complète de l'absorbée — nom, date, type, relais, URL — plus l'ampleur
du geste. Sa ligne étant supprimée, cette entrée est la seule trace qui reste
d'elle : un identifiant nu ne dirait pas six mois plus tard quelle épreuve a
disparu. `absorbed_id` est un `StrictInt` : en mode permissif Pydantic coerce
`true` en `1`, et une case à cocher mal sérialisée supprimerait l'épreuve `1` avec
ses résultats.

**Une limite connue, et elle n'est pas dans ce ticket.** L'issue suppose qu'après
la fusion l'exploitant peut basculer sur l'autre chronométreur (#285). C'est faux
tant que les deux libellés divergent : `admin_actions._require_same_event` refuse
une bascule dont le scrape publie une autre identité — précisément le cas que la
fusion existe pour rapprocher. Faire converger les identités est #289 ; d'ici là
il faut renommer la cible (`PATCH /admin/courses/{id}`, `courses:write`) avant de
pouvoir basculer.
