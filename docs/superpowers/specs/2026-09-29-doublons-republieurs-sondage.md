# Sondage : doublons des republieurs (runnerbreizh), 29/09/2026 (#974)

Rapport de terrain, normatif : il prime sur tout design ou plan qui en
divergerait. Question posée par la décision du 29/09 sur #974 : laquelle des deux
pistes fait sortir les 4 paires runnerbreizh de la liste des doublons suspects
sans nouveau faux positif ?

- **Piste A, « fournisseur republieur »** : une épreuve d'un republieur
  (runnerbreizh, et peut-être t2area) est rapprochée de toute épreuve d'un autre
  fournisseur de même `event_type`, même `is_relay`, à ±3 jours.
- **Piste B, « recouvrement d'athlètes »** : deux épreuves à ±3 jours, de même
  `event_type`, dont au moins 3 athlètes et la moitié des résultats de la plus
  petite sont communs (même `athlete_id`, quel que soit le temps).

## Constat préalable : le motif #910 existe déjà

#974 a été ouverte le 24/09. Le 28/09, #910 a livré le 4e motif de
`course_duplicates`, « mêmes participants à la même date » (`same_finishers`) :
même athlète **et** même temps de finisher, au moins 3 lignes et la moitié des
résultats de la plus petite épreuve, ±3 jours, sans condition de nom, de
fournisseur ni de `is_relay`. Le tableau de production de #910 liste
précisément les 4 paires de #974 (117/799, 176/718, 170/187, 596/753), avec
leurs effectifs d'athlètes communs au même temps : 309, 268, 225, 108. C'est
une variante stricte de la piste B. La question devient donc : ce motif les
sort-il, et l'une des deux pistes ajoute-t-elle quelque chose ?

## Protocole

Aucun accès à la production. Mesures sur une **copie** de la base de
développement (`backend/triathlon.db`, 72 épreuves du 12/09/2025 au 07/06/2026,
10 873 athlètes, 0 paire écartée), migrée à la tête courante, sans aucun appel
réseau. La base de dev ne contient **aucune** épreuve runnerbreizh ; les 4 paires
y ont été reconstruites, par le chemin d'import réel
(`import_service.persist_results`, donc résolution d'identité et dérivation du
statut comprises) :

| Paire prod | Primaire (fournisseur) | Republication runnerbreizh | Date | Type | Résultats | Communs / au même temps | TCN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 117 / 799 | « Les triathlons de Quiberon Open M » (prolivesport) | « Triathlon de Quiberon M » | 06/09 et 07/09/2025 | triathlon-m | 369 / 322 | 309 / 309 | 9 / 0 |
| 176 / 718 | « DUATHLON COUERON » (timepulse) | « Couëron Duathlon S » | 05/10/2025 | duathlon-s | 310 / 270 | 268 / 268 | 28 / 0 |
| 596 / 753 | « 5e Duathlon Nozéen 2025 - Duathlon S - En individuel (OPEN - Non sélectif) » (klikego) | « Duathlon Nozéen S Open » | 13/04/2025 | duathlon-s | 149 / 135 | 109 / 108 | 15 / 0 |
| 170 / 187 | **épreuve réelle de dev n° 67**, « Triathlon de Carnac 2025 - Triathlon M » (sportinnovation) | « Triathlon de Carnac M » | 05/10/2025 | triathlon-m | 261 / 261 | 225 / 225 | 0 / 0 |

**Colonne TCN** : elle reprend le `tcn_count` des primaires relevé par #974
(28 pour Couëron, 15 pour Nozéen), qui diffère des lignes TCN **en double**
chiffrées par #910 en production (24 et 9) : les deux requêtes ne comptent pas la
même chose, et aucune n'a été rejouée ici. Sans effet sur la mesure, puisque
aucun motif ne lit le club ; mais la reconstruction n'est pas une copie de la
production. La preuve que les 4 paires partagent leurs finishers au même temps
repose sur la requête SQL de production de #910 (309, 268, 225 et 108 lignes),
pas sur une mesure de ce sondage.

Côté republication : ni dossard ni club (comme le site), 3 lignes
`?DOSSARD #…` par paire, et des coureurs propres à la republication pour
atteindre l'effectif. Carnac est la seule paire dont la primaire est réelle :
225 de ses 261 finishers, tirés au hasard (graine fixe), sont republiés sous
leurs nom, prénom et temps d'origine. Script de mesure : jetable, non versionné
(il n'écrit que dans la copie).

## Mesures

| Mesure | Base de dev seule | Dev + 4 paires |
| --- | --- | --- |
| `find_candidates` (4 motifs actuels) | 0 paire | **4 paires, toutes `same_finishers`**, les 4 attendues |
| Piste A, republieurs {runnerbreizh} | 0 (aucun republieur) | 4, les 4 attendues |
| Piste A, republieurs {runnerbreizh, t2area} | 0 | 4, les 4 attendues |
| Piste B, même `event_type` | 0 | 4, les 4 attendues |
| Piste B, tout `event_type` | 0 | 4, les 4 attendues |
| Épreuves distinctes (hosts différents) de même type, même relais, ±3 j | 3 | 7 |

Les trois motifs historiques (`same_source_url`, `shared_event_id`,
`close_names`) ne sortent aucune des 4 paires : noms comparables différents,
URL et hosts différents, runnerbreizh hors `PLATFORMS_WITH_EVENT_ID`. Le constat
de #974 sur ces trois motifs est confirmé.

### Ce que coûte la piste A

Son seul discriminant est (type, relais, ±3 jours). La dernière ligne du tableau
mesure combien d'épreuves **réellement distinctes** partagent ce triplet sur la
seule base de dev : 3 paires pour 72 épreuves, par exemple « LE NORTH MAY »
(timepulse, triathlon-m, 07/06/2026) et « Triathlon de la Côte de Granit Rose »
(breizhchrono, 06/06/2026), ou « LE NORTH MAY » S et « Triathlon de Vierzon S »
le même jour. Une republication runnerbreizh de l'un de ces événements sortirait
aussi appariée à l'autre : c'est un faux positif par construction, dont le nombre
croît avec le carré du nombre d'épreuves d'un week-end chargé (la production en
compte 796). Elle ne voit pas non plus un republieur absent de sa liste, et elle
apparierait l'épreuve runnerbreizh sans jumeau (192, Triathlon de Nantes XS) à
toute épreuve XS du même week-end. Écartée.

### Ce que change la piste B

Même rappel que `same_finishers` sur les 4 paires (Nozéen passe à 109 communs
contre 108 au même temps, sans effet sur le seuil de 67,5). Elle relâche l'égalité
de temps et ajoute l'égalité de type : le premier relâchement n'a rien à
rattraper ici (les 4 paires ont leurs temps égaux en production, #910), le second
ferait perdre les doublons à type divergent que `same_finishers` sort déjà
(RED OUF, Châtelaillon, #910). Rien à gagner, un garde-fou (le temps) à perdre.

## Conclusion

Aucun nouveau motif. Les 4 paires sortent déjà, sous « Mêmes participants à la
même date » (#910), sans aucun faux positif sur la base de dev ni sur les tests
de doublons existants. Livré pour #974 : des tests de non-régression qui figent
les 3 paires non encore couvertes (Couëron, Carnac, Nozéen, avec ses 109 communs
dont 108 au même temps ; Quiberon l'était par #910), et un test qui garde la
porte fermée à la piste A (une republication sans jumeau n'est pas appariée à une
épreuve distincte du même type le même week-end).

## Limites et suites

- La confirmation en production reste à faire à la main : l'écran des doublons
  suspects doit lister les 4 paires. Si l'une manque, c'est que ses temps
  divergent en base, et il faut re-sonder avant tout seuil.
- Le traitement des paires (fusion, cible = la primaire, qui porte clubs et
  dossards) est une opération de production, consignée dans #1009.
- La date de l'épreuve 192 n'est pas connue ici : son absence de jumeau est
  reprise de #974, non remesurée.
