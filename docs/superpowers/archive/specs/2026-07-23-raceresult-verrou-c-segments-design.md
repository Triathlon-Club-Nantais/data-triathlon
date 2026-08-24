# RaceResult — élargir le verrou C : récupérer les splits intermédiaires

**Issue** : #84 (suivi de #60 / PR #83). **Date** : 2026-07-23.
**Refs** : `2026-07-19-raceresult-api-sondage.md` §4.2 (amendé), §12.2 ;
`2026-07-23-raceresult-listes-hidden-design.md`.

## Problème

Dans le pipeline de construction des segments (`_build_result`), une cellule de
split devient un `segment` si, une fois son rang suffixé décollé, elle passe
`_RE_DUREE` :

```python
r.segments = [
    (label, normalize_time(valeur))
    for label, col in segments
    if col < len(ligne)
    and (cellule_brute := _clean_cell(ligne[col]))
    and (valeur := _strip_rank_suffix(cellule_brute))   # ← regex STRICTE (§12.2)
    and _RE_DUREE.match(valeur)
] or None
```

`_strip_rank_suffix` emploie `_RE_RANG_SUFFIXE_STRICT` : le **point final est
exigé** (`(5.)`), forme attestée pour `nom`/`club`/`temps` où une parenthèse
finale sans point est un contenu légitime (`'TCN (44)'`, `'TCN (1)'`) — arbitrage
§12.2, conservé.

Or la colonne de split intermédiaire de RaceResult porte cette expression
(mesurée sur 410891, liste `Classement général inter 2`, colonne `InterSemi`) :

```
iif([STATUS]<>2;[InterSemi]) & iif([STATUS]=0 AND [InterSemi]>0;" (" & [InterSemi.OVERALL] & ")";"")
```

Le suffixe de rang est apposé **sans point** (`" (" & [InterSemi.OVERALL] & ")"`),
et **seulement si `STATUS=0`** (finisher). Conséquences, sur les 122 lignes du
groupe 28 KM :

| Statut | Cellule | `_strip_rank_suffix` (strict) | `_RE_DUREE` | Résultat actuel |
| --- | --- | --- | --- | --- |
| Finisher (110) | `'2:05:29 (2)'` | inchangée (pas de point) | rejette | **split perdu** |
| DNF (1, bib 804) | `'2:04:40'` | inchangée (nue) | passe | **split** |
| DNS/vide (11) | `''` | — | — | rien |

**Incohérence** : sur une même épreuve, l'unique DNF porte *plus* de données de
split que les 110 finishers. Trompeur en affichage. Figé aujourd'hui par
`test_scrape_event_all_410891_hidden_fuite_un_split_pour_un_dnf`.

## Décision d'arbitrage

Deux voies (§ Piste de l'issue) : **cohérence all-or-nothing** (refuser le split
nu quand le contest mêle décoré/nu → 0 split partout) vs **récupération
maximale** (décoller aussi le rang sans point pour capter les finishers).

**Retenu : récupération maximale** (décision lead, 2026-07-23). Elle récupère
**111 splits réels** sur 122 lignes — donnée réelle aujourd'hui perdue (§4.2) —
et supprime l'incohérence *par récupération*, non par suppression. L'option
all-or-nothing jetterait ces 111 valeurs pour préserver une symétrie à zéro.

## Solution

Chirurgicale, cantonnée au pipeline segment. **Aucune** modification de
`_RE_DUREE`, `normalize_time`, ni du chemin `nom`/`club`/`temps`.

1. **Nouveau helper `_strip_rank_suffix_segment(valeur)`** utilisant la regex
   **permissive** `_RE_RANG_SUFFIXE` (point facultatif, déjà employée pour
   `sexe`/`categorie`). Il décolle `(2)` comme `(2.)`.

2. **Le pipeline segment appelle ce helper** au lieu de `_strip_rank_suffix`.

3. **`_strip_rank_suffix` (strict) inchangé** pour `nom`/`club`/`temps`.

4. **Extracteur privé partagé** `_decoller_rang(valeur, motif)` pour ne pas
   dupliquer la logique entre les deux helpers.

### Pourquoi le permissif est sûr *ici* — et refusé ailleurs

L'arbitrage §12.2 (point exigé) protège du texte libre : décoller `(1)` de
`'TCN (1)'` fusionnerait deux équipes distinctes. Ce risque **n'existe pas pour
un segment**, car le pipeline garde ensuite par `_RE_DUREE` :

- `'2:05:29 (2)'` → décollé `'2:05:29'` → `_RE_DUREE` **passe** → split récupéré.
- `'TCN (1)'` → décollé `'TCN'` → `_RE_DUREE` **rejette** → aucun dégât.
- `'2:04:40'` (nue) → aucun suffixe → inchangée → `_RE_DUREE` passe → split conservé.

Le point-fixe : sur une durée, une parenthèse finale `(N)` ne peut être qu'un
rang (aucune durée légitime ne se termine par un code départemental). La forme
sans point, non attestée en 2026-07-19 (§12.2), l'est désormais sur 410891 ; elle
ne remet pas en cause l'arbitrage §12.2, elle en délimite la portée : **stricte
pour le texte libre, permissive pour les durées gardées**.

### Non-finishers et segments

Le nettoyage #60 (`if r.status in _NON_FINISHERS: total_time="" ; ranks=None`)
**ne vide pas** `segments` : un intermédiaire franchi avant l'abandon est une
donnée réelle. Le DNF 804 conserve donc légitimement `('10KMS', '02:04:40')`.
Cohérent avec la récupération des finishers : les 122 lignes portent leurs splits
réels, sans exception de statut.

## Tests (TDD)

1. **Helper** `_strip_rank_suffix_segment` (paramétré) :
   `'2:05:29 (2)'`→`'2:05:29'`, `'33:18 (10)'`→`'33:18'`, `'2:08:00 (1.)'`→`'2:08:00'`
   (point toléré), `'2:04:40'`→`'2:04:40'` (nue), `''`→`''`.
2. **Non-régression du strict** : `_strip_rank_suffix('TCN (1)') == 'TCN (1)'`
   (le nouveau helper ne contamine pas l'ancien).
3. **`_build_result`** : une cellule de segment `'2:05:29 (2)'` produit un split ;
   `'TCN (2)'` en colonne segment ne produit rien (`_RE_DUREE` rejette après
   décollage — filet de sûreté du permissif).
4. **Non-régression 410891, mise à jour** : renommer
   `..._fuite_un_split_pour_un_dnf` → `..._recupere_les_splits_intermediaires` ;
   assertion `len(avec_splits) == 111`, DNF 804 toujours présent avec son split,
   les 11 lignes vides sans segment.

## Hors périmètre

- `_RE_DUREE`, `normalize_time`, chemin `nom`/`club`/`temps` : inchangés.
- Le trou `OuStatut([Temps])` (§12.1) : autre ticket.
- L'élargissement aux listes `hidden` (§4.2, préalable réconciliation contest) :
  déjà livré par #60 pour la jointure dossard ; le présent correctif est
  orthogonal (il agit sur la forme des valeurs, pas sur la sélection des listes).

## Documentation à amender

- Sondage §4.2 : verrou C **fermé pour les segments** (récupération, 111 splits).
- Sondage §12.2 : préciser la portée (stricte texte libre / permissive durées).

`AGENTS.md` ne mentionne pas le verrou C (vérifié) : rien à y amender.
