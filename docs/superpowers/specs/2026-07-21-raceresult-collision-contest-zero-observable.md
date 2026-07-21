# RaceResult — rendre observable la collision de dossard du repli `Contest="0"`

**Issue** : [#65](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/65)
(fille de #50). **Design** — 2026-07-21.

## 1. Problème

Le correctif K1/K2 de #59 qualifie les `Course` d'une épreuve RaceResult en
`Contest="0"` par un critère **tout ou rien** (`_groupes_zero_fiables`) : le
libellé de groupe de niveau 0 n'est retenu comme qualifiant que si **tous** les
libellés de l'épreuve recoupent `config["contests"]`. Sinon, repli : aucun
qualifiant, une `Course` unique où la fusion par dossard dédoublonne.

L'issue #65 nomme deux angles morts, **non vérifiables au panel actuel** (aucune
épreuve sondée ne les exerce) :

- **§13.17 du sondage** — aucune épreuve **mixte** `Contest="0"` + `Contest!="0"`
  n'existe au panel. Le comportement du critère sur cette forme n'est pas
  vérifié.
- **§13.19 du sondage** — angle mort **symétrique** du défaut corrigé. Le repli
  « aucun qualifiant » range toutes les lignes d'une épreuve `Contest="0"` non
  corroborée dans une `Course` unique. Si une telle épreuve avait à la fois un
  libellé étranger (qui disqualifie le groupement) **et** des contests réellement
  disjoints partageant des dossards, la fusion par clé `("", dossard)` ferait
  arbitrer `_prefer` entre **deux personnes différentes** au même dossard, et en
  écraserait une **sans trace**.

Sur 409130 la collision est sans effet **par mesure** (union = 529 personnes
distinctes), pas par construction. Le sondage conclut que **le choix reste le
bon** — il échange une duplication *prouvée* (302 dossards) contre une collision
*jamais observée* — mais que les deux branches du repli sont **silencieuses**, et
donne le remède attendu : « Signal à guetter si le cas se matérialise ».

## 2. Ce que cette tâche fait — et ne fait pas

**Fait** : rendre l'angle mort **observable** et **épingler** la forme non
vérifiée. On ne ferme pas le trou (le comportement reste inchangé) ; on le rend
bruyant, en cohérence avec la garde structurante du module — « erreur bruyante et
réversible plutôt qu'amputation muette ».

**Ne fait pas** (délibérément) : aucun changement de la clé de fusion, aucune
détection dure, aucun refus. Le sondage établit que le compromis est le bon et
interdit d'arbitrer sur des données non vérifiées. Arbitrer autrement rejouerait
exactement le mode de défaillance dénoncé : une règle calibrée sur ce qui n'a
jamais été observé.

## 3. Conception

### 3.1 Instrumentation de la collision (§13.19)

Dans la boucle de fusion de `scrape_event_all`, sur une clé `(libellé, dossard)`
**déjà occupée**, émettre un `logger.warning` **uniquement** quand les deux
résultats portent des **identités d'athlète incompatibles**.

Nouveau helper :

```python
def _identites_incompatibles(a: ScrapedResult, b: ScrapedResult) -> bool:
    """Vrai si a et b nomment deux athlètes **distincts** — jamais si l'un est anonyme."""
```

- **Repli d'enrichissement, pas collision** : si l'un des deux côtés n'a aucun
  nom (une liste qui ne porte pas le patronyme, cas nominal de la fusion
  multi-listes), la fonction rend `False`. On ne veut alerter que sur deux
  identités **toutes deux renseignées** et différentes.
- **Comparaison tolérante** : `(nom, prénom)` pliés en minuscules **et** accents
  neutralisés (réutilise la table `_ACCENTS` déjà présente dans le module), pour
  qu'une simple divergence de casse ou d'accent (« José » / « JOSÉ ») ne génère
  pas de faux positif.

La boucle de fusion devient :

```python
cle = (libelle, r.bib_number)
ancien = fusion.get(cle)
if ancien is not None and _identites_incompatibles(r, ancien):
    logger.warning(
        "RaceResult %s : dossard %s en collision sous le qualifiant %r — "
        "deux identités distinctes (%s / %s), une sera écrasée sans trace "
        "(cf. #65 §13.19)",
        event_id, r.bib_number, libelle or "(aucun)",
        _identite_lisible(ancien), _identite_lisible(r),
    )
if ancien is None or _prefer(r, ancien):
    fusion[cle] = r
```

Le **comportement de fusion ne change pas** : on log, puis `_prefer` tranche
comme aujourd'hui. `_identite_lisible` est un petit formateur `"NOM Prénom"` pour
le message (peut être inline si trivial).

**Propriété voulue** — comme les autres gardes du module, **muette sur tout le
panel réel** : une collision d'identités sur une même clé n'arrive pas dans les
chemins qualifiés (le dossard est unique par contest, et deux listes d'un même
contest décrivent la même personne). L'instrumentation ne protège que des formes
**non observées**, ce qui est précisément son objet.

**Portée générale assumée** : la garde est posée sur toute clé de fusion, pas
seulement sur le repli `libelle == ""`. C'est plus simple et strictement plus
sûr — une collision d'identités sous un contest explicite serait tout aussi
anormale et mérite le même signal. Le message rend le qualifiant (`(aucun)` pour
le repli) afin que le cas exact du §13.19 reste identifiable dans les logs.

### 3.2 Épinglage du cas mixte (§13.17)

Tests de **caractérisation** (aucune épreuve du panel ne l'exerce) figeant le
comportement actuel de la forme mixte `Contest="0"` + `Contest!="0"`, pour qu'un
changement futur soit détecté :

1. **Mixte, groupe `Contest="0"` corroboré** → les deux voies qualifiées,
   `Course` distinctes (le `Contest!="0"` par `contests[contest]`, le
   `Contest="0"` par son groupe fiable).
2. **Mixte, libellé `Contest="0"` étranger** → voie `!="0"` qualifiée, voie `"0"`
   repliée sur le nom d'épreuve nu. Un dossard partagé entre les deux voies
   produit **deux `Course`** (clés de fusion distinctes). Comportement épinglé
   **tel quel** — c'est l'état non vérifié que #65 documente, pas une cible à
   corriger.

### 3.3 Tests de l'instrumentation (§13.19)

Avec `caplog` :

1. Collision de **deux identités distinctes** sur `("", dossard)` (repli non
   qualifié) → **un** warning émis, une seule ligne retenue (celle de `_prefer`).
2. Fusion **même personne**, un côté anonyme (liste sans nom) → **aucun**
   warning, club/temps enrichis comme aujourd'hui.
3. Fusion **même personne** nommée identiquement sur deux listes → **aucun**
   warning.
4. (unitaire) `_identites_incompatibles` : `False` si un côté anonyme ; `False`
   sur divergence de casse/accent uniquement ; `True` sur deux noms pleins
   distincts.

## 4. Fichiers touchés

- `backend/app/scrapers/raceresult.py` — helper `_identites_incompatibles`
  (+ formateur d'identité), warning dans la boucle de fusion de
  `scrape_event_all`. Aucun autre chemin modifié.
- `backend/tests/test_raceresult.py` — tests §3.2 et §3.3.
- `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` — note de clôture
  aux §13.17 et §13.19 : l'angle mort est désormais **observable** (renvoi #65),
  pas fermé ; le cas mixte est épinglé par test.

## 5. Critères d'acceptation

- La suite `uv run pytest -m "not integration"` reste verte, instrumentation
  comprise, **sans** nouveau warning sur les fixtures du panel existant.
- Une collision d'identités distinctes sur une clé de fusion émet exactement un
  `logger.warning` mentionnant dossard, qualifiant et les deux identités.
- Une fusion d'enrichissement légitime (un côté anonyme, ou même identité)
  n'émet **rien**.
- Le comportement observable de `scrape_event_all` (nombre de `Course`, lignes
  retenues) est **inchangé** sur tous les cas existants.
