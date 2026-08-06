# ok-time.fr (issue #52)

ok-time.fr (issue #52) se lit sur une API JSON WordPress publique
(`/wp-json/gmcap/v1/evenements/{id}/results`) : **un seul appel** rend
l'événement entier, toutes épreuves comprises — ni Playwright ni parsing HTML
sur le chemin nominal. Les points de passage sont **cumulés** et différenciés en
durées de segment, rangées dans `segments` (chemin générique) avec les libellés
de la source : les `id` de points ne sont pas sémantiques (`12|2` vaut « T2 »
sur une épreuve, « VELO » sur une autre) et 55 des 99 courses du panel sortent
du motif triathlon. Ces libellés sont rendus **verbatim** par le front, via le
chemin générique de `lib/utils/splits.ts` (`splitColumns` / `splitSegments`) : à
défaut de clé canonique, les colonnes viennent des libellés publiés — sans lui, les
splits d'ok-time, RaceResult et Chronoplace étaient stockés mais invisibles.
Statuts : **DNS, puis DSQ, puis DNF** (la source cumule des drapeaux
contradictoires, et la disqualification prime sur l'abandon), et le repli
`finisher` d'une course non chronométrée se mesure **au seuil** — au plus
`max(1, 10 %)` de participants chronométrés — jamais à l'égalité stricte à zéro,
qu'un seul temps saisi à la main suffisait à désarmer, faisant classer toute une
course d'enfants DNF. Le type de course est classé sur `title_course`, le titre
d'événement servant d'**appoint** : `classify_event_type(texte, contexte=…)` ne
consulte le contexte que si l'épreuve ne nomme aucun sport (« Format M
individuel » d'un SwimRun), et la taille de l'épreuve prime toujours sur celle du
contexte. Ne pas revenir à la **concaténation** des deux titres : elle classait le
« Trail 12 km » d'un « Triathlon de X » en `triathlon`, qui s'affichait comme tel
et **survivait** à `federal_only=true`. Deux
formes d'URL sont supportées, `classement.ok-time.fr/<id>[/race/<raceId>]` et
`ok-time.fr/evenement/<slug>/` — cette dernière résolue par un GET HTML dont
`_resolve_event_id` **vérifie la page atterrie** (un slug retiré est redirigé vers
le listing générique, qui porte les liens de classement de tous les événements :
en retenir le premier importerait un événement étranger sous la `source_url`
demandée, sans erreur) ; les préfixes `/course/` et `/competition/` sont
**obsolètes** et rejetés avec un message qui le dit — trois URLs du Sheet en
relèvent et deviennent, ok-time étant désormais supporté, des épreuves en erreur
dans les bilans plutôt que des liens ignorés. Vérité d'API (panel de 21
événements / 99 courses / 12 644 participations) :
`docs/superpowers/specs/2026-07-26-oktime-scraper-design.md`.

**Fan-out par course** (#221) — comme Chronoweb, un seul GET rend l'événement
entier ; le gain n'est pas la requête économisée, mais l'**intégrité du cache
TTL**. Chaque course de la charge (`charge["data"]`, identifiée par
`epreuve_id`) reçoit sa propre `source_url` canonique
`classement.ok-time.fr/<eventId>/race/<epreuveId>` — donc son propre TTL,
au lieu d'un TTL commun à l'événement entier qui reconstruisait toutes les
courses à chaque re-scrape. Le contrat est celui du fan-out Klikego (#156) :
`cache_probe(sub_url)` saute une course déjà fraîche (comptée dans
`heats_cached` + `cached_urls`, jamais notifiée à `on_heat_start`), une course
en échec est isolée dans `trace.failures` sans arrêter les autres, et
`on_heat_start(slug, label, index, total)` reçoit `total` = nombre à scraper
(pas nombre énuméré), sans quoi la progression sauterait des indices sur un
ré-import majoritairement caché. `scrape_event_all(url)` (mono-course sur
tout l'événement) reste disponible pour l'échappatoire `--single-heat` et les
tests unitaires.
