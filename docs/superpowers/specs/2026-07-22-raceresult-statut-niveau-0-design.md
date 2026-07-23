# RaceResult — un statut à la profondeur 0 ne doit plus perdre son statut

Issue [#64](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/64),
issue de la revue de #59, sous-issue de #50. Latent : 9 épreuves sondées, aucun
cas observé (cf. §13.15 du sondage d'API).

## Problème

`_iter_groups` (`app/scrapers/raceresult.py`) descend l'arbre `data` en traitant
**inconditionnellement** la profondeur 0 comme un contest :

```python
if profondeur == 0:
    groupes += _iter_groups(contenu, contest=libelle, statut=statut, profondeur=1)
```

Un groupe de niveau 0 qui est en réalité un **statut** — `{'#2_Abandons': [...]}`
— produit donc `contest="Abandons", statut=""`.

Le correctif K1/K2 du §3.1 (issue #59) a fermé la moitié « `Course` fantôme » du
défaut : à `Contest != "0"` le libellé de groupe n'est plus consulté (le contest
est explicite), et à `Contest == "0"` un `Abandons` absent de `contests`
disqualifie le groupement (`_groupes_zero_fiables`). **Reste la perte de
statut** : sur une liste `Contest != "0"`, le contest « Abandons » est écrasé par
le contest explicite, mais le `statut=""` fait passer des abandons pour des
finishers (`services/mapping.derive_status` retombe sur « finisher si temps »).

## Correctif : croisement avec `contests`

À la profondeur 0 **uniquement**, un libellé est reclassé en **statut** (au lieu
de contest) si et seulement si :

1. `derive_status_from_label(libellé)` le reconnaît — table **fermée et déjà
   mesurée**, employée à la profondeur ≥ 1 pour exactement cet usage ; l'étendre
   à la profondeur 0 n'invente aucun vocabulaire ; **et**
2. le libellé est **absent** de `contests` (les valeurs du dict de config,
   normalisées `strip().lower()`).

Sinon, comportement inchangé : le libellé nomme le contest.

La condition 2 lève le **risque symétrique** que la revue avait laissé ouvert (un
contest légitimement nommé d'après un jeton de statut serait mal classé) : un tel
contest figure dans `contests`, il reste donc un contest. Le croisement s'appuie
sur l'autorité déjà en place dans le module — `contests` fait foi pour la
qualification (§3 du sondage), `_groupes_zero_fiables` s'en sert déjà.

Un groupe reclassé porte `contest=""` (hérité) et `statut=<STATUS reconnu>`.

## Détails d'implémentation

- **`_contests_normalises(contests) -> frozenset[str]`** : extrait la
  normalisation aujourd'hui inline dans `_groupes_zero_fiables`
  (`{str(v).strip().lower() for v in contests.values() if str(v).strip()}`),
  réutilisée aux deux endroits. Supprime la duplication.
- **`_iter_groups`** reçoit `contests_connus: frozenset[str] = frozenset()`,
  propagé dans toute la récursion. Le défaut vide préserve le comportement des
  appels de test directs qui ne passent pas de contexte de contest.
- **Appel de production** (`scrape_event_all`) : calcule `contests_connus` une
  fois et le passe à `_iter_groups`.

## Non-régression sur `_groupes_zero_fiables`

Un libellé n'est reclassé que s'il est **absent** de `contests`. Or `fiable_zero`
exige que **tous** les libellés de niveau 0 soient des valeurs de `contests`. Un
libellé reclassable disqualifiait donc **déjà** `fiable_zero`. La reclassification
ne peut donc jamais faire basculer un `True` en `False` : elle préserve seulement
le statut là où il était perdu. Le libellé reclassé sort avec `contest=""`, qui
disqualifie `fiable_zero` exactement comme le faisait le libellé étranger avant.

## Tests (TDD)

1. `_iter_groups` — niveau 0 `{'#2_Abandons': [...]}`, `contests_connus` sans
   « abandons » → `[("", "Abandons", [...])]` (statut préservé).
2. `_iter_groups` — **risque symétrique** : niveau 0 `Abandons` **présent** dans
   `contests_connus` → reste contest `[("Abandons", "", [...])]`.
3. `_iter_groups` — un libellé de contest ordinaire (`Distance M`) reste contest,
   avec ou sans `contests_connus`.
4. Intégration `scrape_event_all` — liste `Contest="1"` dont `data` porte un
   groupe de niveau 0 `#2_Abandons` : le participant sort qualifié par le contest
   explicite **et** avec statut DNF (le bug end-to-end).

## Portée

~10 lignes. N'ajoute aucun vocabulaire, ne touche ni les temps, ni les rangs, ni
la fusion. Ne modifie pas `_groupes_zero_fiables` autrement que par l'extraction
du helper.
