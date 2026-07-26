# Correctifs RaceResult après revue de branche — reprise en session neuve

**État de la branche : ❌ non mergeable.** Quatre pertes de données silencieuses,
plus trois trous de test. Aucune refonte nécessaire — les correctifs sont
circonscrits.

**Branche** : `50-feat/scrapers-moteur-raceresult-générique…` (worktree du même nom)
**Plage** : `c934b044..HEAD`, 20 commits. Dernier commit : `c795f03`.
**Module** : `backend/app/scrapers/raceresult.py` (778 lignes)
**Tests** : `backend/tests/test_raceresult.py` — 741 unitaires verts, ruff vert.

## Lire ceci d'abord

| Document | Rôle |
| --- | --- |
| `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` | **Vérité d'API.** Prime sur le plan et sur le design. À compléter (§« Corrections à porter au sondage » plus bas). |
| `docs/superpowers/plans/2026-07-19-raceresult-scraper.md` | Plan d'origine, **porte un bloc ERRATA en tête** : son API est fausse. Valeur documentaire seulement. |
| `.superpowers/sdd/progress.md` | Ledger : historique complet des défauts, des arbitrages et des limites assumées. |

## Le mode de défaillance de cette branche

À lire avant de toucher au code, parce qu'il s'est **reproduit deux fois** sous
des formes différentes.

Le moteur a d'abord été bâti et revu six fois contre **une seule épreuve**, sur
une route d'API héritée : il ne fonctionnait que là. Refondu sur un sondage à
8 épreuves, il a de nouveau été pris en défaut par une revue qui a sondé
**107 eventId hors panel**. À chaque fois, la cause est la même : *une
généralisation à partir de ce qui a été vu*, jamais confrontée à ce qui n'a pas
été vu.

**Règle de travail pour la suite** : ne corrige aucun de ces défauts sans
exécuter le moteur sur l'épreuve réelle qui l'a révélé (l'eventId est donné pour
chacun), **et** sur au moins deux épreuves qui ne l'exposaient pas, pour vérifier
l'absence de régression. Les fixtures et les tests unitaires viennent *après* la
mesure, jamais avant.

L'API est publique, en lecture seule, sans authentification. Attention toutefois :
un balayage à 24 threads a déclenché un **blocage réseau côté RaceResult**
(rétabli après ~45 s). Sonder en série, avec ~3 s de délai.

---

## Défauts bloquants

### C1 — Une liste d'affichage non-`hidden` fait perdre 100 % des temps

**Où** : `raceresult.py:172` (`_iter_list_specs`) et `raceresult.py:337` (`_role`)
**Épreuve de preuve** : **406211** — World Triathlon Para Cup, Besançon
**Mesure** : 42 participants, **42 sans temps**, alors que le temps est dans la ligne.

La docstring de `_iter_list_specs` affirme que les listes d'affichage à formules
`{Selector.Splits}` sont écartées parce qu'elles sont `Mode == "hidden"`. **C'est
faux.** Sur 406211, la seule liste publiée est `'01-Résultats en ligne|LIVE'`,
non-`hidden`, dont la colonne temps vaut :

```
switch([{Selector.Splits}.NAME]=[Finish.NAME];[FinishResult.TEXT];…)
```

`_peel` la réduit à `finishresult.text`, inconnu de `_role`. Le temps atterrit
dans `raw_data` sous la clé d'expression brute, avec sa valeur (`'1:03:01'`).

**Pourquoi c'est bloquant** : sans `total_time`, `services/cache.is_fresh` classe
la Course « en cours » → TTL 10 min au lieu de 30 j → **re-scraping perpétuel**.
Le ledger acceptait ce symptôme sur les 24H Rollers *parce que la source n'a pas
de chrono* ; ici la source en a un et c'est le scraper qui le jette. **Cet
arbitrage ne couvre pas ce cas** — ne pas le réutiliser pour classer C1 sans
gravité.

**Piste** : reconnaître `FinishResult`/`.TEXT` dans `_role`, et surtout ne plus
faire reposer la sélection de liste sur la seule absence de `hidden`. Une piste
plus robuste que d'allonger la table : si aucune liste retenue ne produit de
rôle `temps` alors qu'une colonne de la ligne ressemble à une durée, c'est un
signal exploitable — à instruire, pas à implémenter d'office.

### C2 — Une concaténation imbriquée dans `if(…)` fait perdre tous les splits

**Où** : `raceresult.py:257` (`_peel`)
**Épreuve de preuve** : **401699** — Half Iron du Lac d'Annecy
**Mesure** : 587 participants, **0 segment**.

`_peel` applique ses trois étapes **une seule fois, dans un ordre fixe** :
concaténation (`&`), puis enrobages, puis conditionnelle (`;`). Quand une
concaténation est *à l'intérieur* d'un `if(…)`, l'étape 1 ne la voit pas
(profondeur > 0) et n'est jamais rejouée après l'étape 3.

Comparaison mesurée sur deux listes de la **même** épreuve :

```
RELAIS (sans if) -> peel='natation'                                   => SEGMENT=True
INDIV  (avec if) -> peel='natation & " (" & natation.overall.p & ")"' => SEGMENT=False
```

Les valeurs sont pourtant présentes dans `raw_data` :
`'if([STATUS]<>2;[Vélo] & " (" & [Vélo.OVERALL.P] & ")")' = '2:08:00 (1.)'`.

**Piste** : faire de `_peel` un **point fixe** — boucler tant que la chaîne
change — plutôt qu'un passage ordonné. La docstring actuelle justifie longuement
l'ordre concat→enrobage ; cette justification reste valable, mais l'imbrication
inverse existe aussi en production, donc l'ordre ne suffit pas. Attention à
garantir la terminaison de la boucle.

### C3 — Un rang collé au split fait perdre le split (cause indépendante de C2)

**Où** : `raceresult.py:225` (`_RE_DUREE`) et `raceresult.py:607`
**Épreuve de preuve** : **401699**, liste relais
**Mesure** : `_map_columns` détecte bien `[('Nat. + T1', 7), ('Vélo', 8), ('Course + T2', 9)]`,
et les segments sont malgré tout perdus.

La valeur porte le rang collé, donc `_RE_DUREE` la rejette :

```
'33:18 (10.)'   _RE_DUREE=0   normalize_time='33:18 (10.)'
'2:20:22 (1.)'  _RE_DUREE=0   normalize_time='2:20:22 (1.)'
```

Le module sait déjà décoller un rang suffixé — `_RE_RANG_SUFFIXE`
(`raceresult.py:316`), utilisé pour la forme `"M0M (1.)"` — mais ne l'applique
**jamais** aux valeurs de segment. Et `normalize_time` est permissif : il
laisserait passer `"33:18 (10.)"` tel quel si on relâchait `_RE_DUREE`.

**C2 et C3 frappent la même épreuve par deux chemins distincts : il faut
corriger les deux pour récupérer le moindre split sur 401699.**

### C4 — Vocabulaire de temps franco-centré

**Où** : `raceresult.py:337` (`_role`)
**Épreuve de preuve** : **380823** — Bike & Run de Pontcharra (type supporté par `AGENTS.md`)
**Mesure** : 58 participants, **58 sans temps**, `raw_data` contient `'Finish.GUN': '31:27'`.

```
Arrivée.GUN        -> 'temps_pistolet'
Arrivée.CHIP       -> 'temps'
Finish             -> 'temps'
Finish.GUN         -> ''      <-- perdu
Finish.CHIP        -> ''      <-- perdu
FinishResult.TEXT  -> ''      <-- perdu (cf. C1)
```

La table anticipe les variantes françaises et le `Finish` nu, mais pas les
variantes anglaises suffixées. **Ne pas se contenter d'ajouter ces trois
entrées** : le défaut de fond est qu'une table d'égalités exactes échoue en
silence hors relevé. Préférer une règle de forme (préfixe temps/arrivée/finish +
suffixe `.gun`/`.chip`/`.text`), avec la préférence chip > gun déjà en place.

---

## Défauts non bloquants

### I1 — L'enrobage i18n n'est retiré que des libellés, jamais des cellules

`raceresult.py:396` (`_label_i18n`), appelé uniquement en `raceresult.py:461`.

Sur 401699, la catégorie relais entre en base telle quelle :
`category = '{EN:Men|FR:Masculin}'`. Illisible en UI et non regroupable. La
fonction existe déjà ; il manque son application dans `_clean_cell`.

### I2 — Noms d'équipe passés à `split_athlete_name`

`is_relay` n'est déduit que du libellé de contest (`relais|relay|equipe|équipe`),
qui ne matche ni « Duo » ni « Bike & Run ». Résultat :

- 403144 (Aquaterra, SwimRun L, duo) : `nom='GUILLAUME', prenom='& ANTHONY'`
- 380823 : `nom='Associés', prenom='Les Inconnus'`

Risque : des `Athlete` fantômes via `UNIQUE(nom, prenom, birth_date)`.
**Statut : hypothèse** — mesuré en sortie de scraper, pas instrumenté à travers
`import_service`. À confirmer avant de corriger.

### I3 — `CustomFlag` admis comme segment candidat

`raceresult.py:467`. Sur 406211, la colonne 5 est `CustomFlag` (drapeau) avec le
libellé `{FR:Nat.|EN:Team}` → `"Nat."`, indiscernable de « Natation ».
`peel('CustomFlag')='customflag'` passe `_RE_TOKEN_SIMPLE`. Le faux positif ne se
matérialise que parce que la valeur est `[img:…]`, effacée par `_clean_cell`
donc falsy — **neutralisé par accident, pas par conception**. Le §6 du sondage
demandait une liste d'exclusion explicite (`CustomFlag`, `[LienPhotos]`,
`NATION.IOCNAME`, `Icone("photos")`, `GapTimeTop(…)`) : elle n'existe pas.

---

## Trous de test — 4 mutations survivantes sur 25

Campagne du relecteur : 21 tuées, 4 survivantes. La distinction ci-dessous
importe : **un garde-fou redondant n'est pas un défaut de test**.

| # | Mutation | Nature | Action |
| --- | --- | --- | --- |
| M3 | `raceresult.py:703` — 1re garde de `_prefer` → `if False:` | **Test vacuous.** La garde n'est pas redondante : elle est asymétrique de la seconde (`ancien.status … return False`). Sans elle, un DNF arrivant *en second* n'écrase plus rien. Le commit `0a1536d` porte sur ce bloc et ne l'a pas verrouillé. | Ajouter un test de fusion où la ligne DNF/DNS arrive **après** une ligne muette sans temps. |
| M15 | `raceresult.py:617` — purge des non-finishers → `pass` | **Test vacuous en CI.** L'invariant est couvert, mais uniquement par `test_scrape_event_all_status_jamais_incoherent` (`test_integration_scrapers.py:104`), marqué `integration` — **donc jamais joué en CI**. | Doubler d'un test unitaire sur fixture. |
| M19 | `raceresult.py:594` — précédence groupe/cellule inversée | **Fixture manquante**, pas garde redondante. Aucune fixture n'a un groupe et une cellule aux statuts **divergents**. Les deux ordres divergent dès qu'une liste « Non Partants » contient une cellule `OuStatut` contradictoire. | Ajouter la fixture divergente. |
| M13 | `raceresult.py:220` — `_RE_TOKEN_SIMPLE` accepte les points | **Garde partiellement redondante** : `_role` intercepte `.p` en amont, `_RE_DUREE` filtre en aval. Effet observable nul aujourd'hui — mais I3 montre que la redondance repose sur un accident de valeur. | Test à ajouter, sévérité faible. |

---

## Corrections à porter au sondage

Le sondage d'API est la vérité de référence, **et il est lui-même
sous-échantillonné**. À amender une fois les correctifs faits :

1. **§4** conclut que `Mode != "hidden"` sélectionne les classements publiés, sur
   la foi de 7 épreuves. 406211 l'infirme : sa seule liste non-`hidden` est une
   liste d'affichage `{Selector.Splits}`. Reformuler en critère *nécessaire mais
   non suffisant*.
2. **§6** énumère des colonnes à ignorer qui ne sont pas implémentées (cf. I3).
   Soit les implémenter, soit retirer l'affirmation.
3. **§6** doit intégrer les variantes anglaises suffixées (C4) et
   `FinishResult.TEXT` (C1).
4. Ajouter au panel les épreuves qui ont fait tomber cette version : **401699,
   406211, 380823**, et au moins un swimrun (400001, 409725 ou 403144).

---

## Ce qui est confirmé bon — ne pas défaire

- **Le correctif C-E de la revue précédente tient largement hors panel** :
  `sansNom` vaut 0 ou 1 sur les 13 épreuves sondées. C'était le défaut le plus
  grave de la version précédente ; il est réellement corrigé.
- Route canonique, apex `my.raceresult.com` universel, `TabConfig.Lists`,
  `DataFields` à la racine, descente récursive de `data`, JSON-LD comme unique
  source de date : **revérifiés empiriquement, aucun pris en défaut**.
- Qualification par contest : `n_event_names` monte jusqu'à 11 sur Aquaterra, et
  la mutation « clé de fusion sans contest » est tuée.
- Forme du code : docstrings qui expliquent le *pourquoi*, français correct,
  aucun Playwright, surface publique réduite à `scrape_event_all`.

## Angles morts de la revue — non instruits

À ne pas confondre avec « vérifiés bons » :

- **Représentativité des fixtures : non instruite.** Les payloads n'ont pas été
  re-téléchargés ni diffés contre `raceresult_config_*.json` /
  `raceresult_list_rumilly_m.json`. Une retouche manuelle ne peut être ni
  confirmée ni infirmée. *(Elles ont été régénérées depuis des captures réelles
  lors de la refonte, mais cela n'a pas été revérifié indépendamment.)*
- **Collisions de fusion : partiellement instruit.** Aucune recherche active de
  deux personnes distinctes fusionnées sous une même clé.
- **Aucune épreuve hors France, hors des deux façades tierces, en cours (live),
  ou antérieure à 2024.** Le balayage d'eventId voisins a échoué sur le
  rate-limit ; les 13 épreuves viennent toutes de l'annuaire chronoconsult.
- **6 épreuves sur 13 remontent zéro segment** — dont trois swimruns et un
  championnat de France. C2/C3 en expliquent une partie ; **rien ne prouve
  qu'ils les expliquent toutes**. À re-mesurer après correctifs :
  400001 (Swimrun Côte de Jade), 409725 (Swimrun Thonon), 403144 (Aquaterra).
  `AGENTS.md` revendique qu'« un swimrun multi-legs garde toutes ses étapes » :
  cette phrase est actuellement démentie par la mesure.

---

## Ordre de travail suggéré

1. **C2 + C3 ensemble**, validés sur 401699 (les deux sont nécessaires pour un
   seul résultat observable).
2. **C4**, validé sur 380823 — en visant une règle de forme, pas trois entrées
   de plus dans la table.
3. **C1**, le plus délicat : il touche le critère de sélection des listes, donc
   re-valider tout le panel derrière.
4. **Re-mesurer les 6 épreuves sans segment** et conclure sur les swimruns.
5. Les 4 tests manquants (M3, M15, M19, M13).
6. I1, puis I2 (après confirmation) et I3.
7. Amender le sondage, puis relancer une revue complète.

## Commandes

Depuis `backend/`, jamais de venv à activer :

```bash
uv run pytest -m "not integration" -q          # 741 attendus verts
uv run pytest -m integration -q -k raceresult  # 10 tests réseau réel
uv run ruff check .
```

Sonder une épreuve de bout en bout :

```python
# PYTHONPATH=. uv run python …
from app.scrapers import raceresult
res = raceresult.scrape_event_all("https://my.raceresult.com/401699/results")
print(len(res), sum(1 for r in res if not r.total_time), sum(1 for r in res if r.segments))
```

Vérifier qu'un garde-fou mord (mutation) : muter la ligne de production, lancer
`uv run pytest tests/test_raceresult.py -m "not integration" -q`, compter les
`FAILED`, **restaurer le fichier**. Zéro `FAILED` = test vacuous, garde redondante,
ou mutation sans effet observable — trancher laquelle avant de conclure.
