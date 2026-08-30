# Breizh Chrono (`resultats.` et `live.`)

Breizh Chrono tourne sur le **même back-office que Klikego** : moteur de liste
partagé (`klikego_platform.build_heat_results` — data block `base64` + XOR de 12
champs, paginé par 50, DNF/DNS/DSQ compris) et page détail identique octet pour
octet, d'où `klikego._parse_detail` — à factoriser dans `klikego.py`, jamais à
dupliquer. Une `Course` = **un heat**, nommée `« <Épreuve> - <Heat> »`
(`course_name`) : sans ce suffixe, les six swimruns de Dinard 2025, tous classés
`swimrun`, ne formaient qu'une seule course (#308).

## Deux façades, un même moteur

Le provider matche le host `breizhchrono.com` (host exact ou vrai sous-domaine)
et route sur le sous-domaine :

- `resultats.breizhchrono.com/resultats-courses/{slug}-{event-id}/{heat}` — la
  forme nominale ; **sans** `{heat}`, tous les heats de l'épreuve sont importés ;
- `resultats.breizhchrono.com/bc/resultats/coureur.jsp?ref=&heat=&dossard=` — le
  `dossard` est **ignoré** (l'import reste le heat entier) et le slug en ressort
  vide : ni nom dérivé, ni `source_url` propre
  (`/resultats-courses/-{event-id}/{heat}`). Préférer la forme nominale ;
- `live.breizhchrono.com/external/live5/{index,classements}.jsp?reference=` — et
  `&heat=` optionnel — vers `scrape_live_event_all`. La `reference` **est** la
  clé `ref` du data block ; sans elle, refus avant tout appel réseau. Le host
  live est comparé à l'**égalité**, jamais en sous-chaîne : un `in` routait aussi
  `live.breizhchrono.com.attaquant.tld` vers ce moteur (#432).

Les deux façades produisent des `Course` distinctes — noms et dates divergents,
jusqu'à 2 jours — que `services/course_reconciliation` rapproche par identifiant
de plateforme + slug de heat : **le** cas d'usage réel de la règle R (#289).

La racine `/resultats-courses/{slug}-{id}` ne porte jamais la liste des heats :
elle répond **302** vers l'un d'eux (mesuré à Mesquer 2026). Le 302 est lu
explicitement puis sa cible re-GETée — cette page embarque la même nav
inter-heats. Un refus du garde SSRF (`DomainError`) **remonte** ; toute autre
panne dégrade en heat unique sans libellé.

`BreizhChronoProvider` est un `FanoutProvider` (issue #707), comme Klikego :
une URL **sans** heat déclenche `scrape_event_fanout`/`scrape_live_event_fanout`
(`cache_probe` par heat, `on_heat_start` pour la progression SSE, `FanoutTrace`
pour les 5 compteurs FR-008). Une URL qui fixe déjà un heat (`/…/{heat}`, ou
`?heat=` côté live/`coureur.jsp`) retombe sur le contrat historique
`scrape_event_all`/`scrape_live_event_all` — une seule sous-unité, pas de
fan-out à instrumenter — avec une trace synthétique 1-heat, même patron que
l'échappatoire `single_heat` des autres providers fan-out.

`_fetch_all_heats` exclut aussi les heats non-sportifs par préfixe de slug
(`_is_non_sport_heat` / `_NON_SPORT_HEAT_PREFIXES`) : sur les épreuves
éco-labellisées, Breizh Chrono publie un heat `classement-durable---…` qui
re-classe le MÊME peloton par empreinte carbone plutôt que par temps — pas un
heat sportif distinct. Non filtré, il s'importait comme une épreuve `triathlon`
à part entière avec des « finishers » fantômes, doublant les athlètes de la
vraie épreuve (#703, Trégastel 2026 — 352 finishers fantômes, épreuve id 840).
Sont exclus par le même mécanisme : `classement-general`, `challenge-*`,
`general-*`.

## Les splits fins ne couvrent que le club

Deux étages. Les splits **inter** (checkpoints du `<select name="inter">`) sont
collectés pour **tous** les participants. Les splits **fins**
(`resultat-participant.jsp`) ne sont demandés que pour les athlètes du TCN, via
`core.club.is_tcn` — jamais une liste locale (#76) : « RACING CLUB NANTAIS »
n'est pas le nôtre et ne déclenche aucune requête. Ils **priment** sur les inter,
donc les cinq slots sont remis à zéro avant `_parse_detail`, sans quoi un inter
grossier survivrait à un split fin absent du même segment. Klikego fait la même
remise à zéro mais **restaure** les inter quand la page détail ne rend aucun
split ; ici non — un TCN dans ce cas ressort sans splits. Le heat de chaque
requête est lu dans `raw_data["heat_slug"]`, indispensable dès que les résultats
couvrent plusieurs heats. D'où `breizhchrono` dans
`UNRELIABLE_SPLIT_PROVIDERS` : ses courses sont exclues des statistiques par
segment, un classement bâti sur les seuls membres du club se présenterait comme
complet.

## `officiel` peut être vide : replier sur `reel` (#757)

Le data block partagé (`klikego_platform.parse_data_row`) porte deux champs de
temps d'arrivée : `officiel` (temps canon, décalé par la vague de départ) et
`reel` (chrono net). Le champ nominal est `officiel`, mais certaines épreuves
le publient **vide** et ne renseignent que `reel` — constaté en direct sur
Dinard 2024 (heat `triathlon-distance-olympique`, réf. `…-673`) et Audencia
2024 (heat `triathlon-m`, réf. `…-572`), alors que les mêmes heats côté 2025
(réf. `…-688`, `…-688`) publient `officiel` normalement. Sans repli, `clt`
(`classement`) reste un rang valide mais `total_time` ressort vide : `status`
part vide aussi (le token n'est pas DNF/DNS/DSQ), donc
`services/mapping.derive_status` (`STATUS_FINISHER if total_time else
STATUS_DNF`) reclasse en **DNF** un finisher pourtant classé — d'où des
centaines de participations DNF portant un `rank_overall` peuplé, et le
`rank_gap` massif qui en découle sur les finishers restants
(`services/quality.py`). `parse_data_row` retient donc `officiel.strip() or
reel.strip()`. Mesuré sur prod (2026-08-30) : Dinard 2024 passe de 10
finishers/940 DNF (`rank_gap=776`) à 933 finishers/17 DNF (`rank_gap` résiduel
1, comme la génération 2025) ; Audencia 2024 (`triathlon-m`) de 19
finishers/695 DNF (`rank_gap=674`) à 705 finishers/9 DNF, ranks 1..705 sans
trou.

Les éditions 2024 déjà en base restent polluées tant qu'un rescrape ne les a
pas repassées par le code corrigé — mise à jour **en place**
(`course_id`+`bib_number` inchangés, appariement par dossard dans
`import_service`), pas une purge : la correction ne touche qu'un champ dérivé
par ligne (`status`/`total_time`), pas l'identité de la `Course` (nom, date,
type, relais).

## Dates, types, relais

`_parse_bc_date` cherche une date dans le **HTML entier**, pas dans un élément
ciblé : ISO d'abord (`resultats.`), format FR en repli (`live.`). Côté classique,
une seule date d'épreuve, lue sur la page du heat ou la racine ; injoignable →
WARNING et import sans date (`event_date=None` change la clé d'identité de
`Course`). Côté live il faut **deux** pages, jointes sur le libellé de heat
normalisé (casse, espaces) : `classements.jsp` donne les slugs de heats, leurs
libellés et le slug d'épreuve mais **aucune date** ; `index.jsp` donne le nom
accentué (« Côte d'Emeraude », que le slug aplatit en « Cote Demeraude ») et
**une date par heat** — à Dinard 2025, le trail court le 12/09 et les triathlons
les 13 et 14/09.

Type d'épreuve : `classify_event_type(heat, contexte=slug)` côté classique,
**heat seul** côté live (le slug d'épreuve y nomme une discipline vedette qui
fausserait le type des autres heats). Relais : `heat_is_relay` sur le libellé et
le slug, plus un signal propre à Breizh Chrono — un slug relais dont le libellé
manque se termine par « --- », sans qu'aucun mot ne le dise.

Volumes mesurés : La Baule Audencia 2024, heat `triathlon-s-light`, 591
participants dont 483 finishers ; Mesquer 2026, 8 heats depuis une racine en 302.
Tests : `backend/tests/test_breizhchrono.py`, réseau réel dans
`backend/tests/test_integration_scrapers.py` (marker `integration`).
