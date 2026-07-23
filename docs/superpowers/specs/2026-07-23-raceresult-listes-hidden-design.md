# RaceResult — élargir aux listes `hidden` par jointure sur dossard (issue #60)

**Statut : design validé, adossé à des mesures réelles du 2026-07-23.** Ce
document lève les deux verrous consignés au §4.2 du sondage d'API
(`2026-07-19-raceresult-api-sondage.md`) et **amende** ce §4.2 : la mesure
d'origine (`'PTS5 Men'` ↔ `'PTS5 M'`) le décrivait comme un écart de graphie ; la
re-mesure montre un écart de **partition**, qui invalide l'approche « réconcilier
les libellés » et impose une jointure par dossard. Le sondage prime sur le
design ; ce document apporte la mesure qui corrige le sondage.

## 1. Ce que #60 demandait, et pourquoi la lettre est fausse

L'issue enchaîne deux étapes : (A) « réconcilier les libellés de contest », puis
(B) « élargir aux listes `hidden` ». Le sondage §4.2 fondait (A) sur une seule
observation de 406211 : le classement `hidden` indexe ses contests sous
`'PTS5 Men'`, les listes publiées sous `'PTS5 M'` — un écart anglais/abréviation,
apparemment réconciliable par appariement de libellés.

**Mesuré le 2026-07-23, la partition elle-même diffère** (406211, apex) :

| Groupe du classement `hidden` (Contest=0) | Contest publié correspondant |
| --- | --- |
| `PTS2 Men`, `PTS3 Men` | **fusionnés** en `PTS2-3 M` (contest 6) |
| `PTVI Men` | **éclaté** en `PTVI1 M` (c2) / `PTVI2-3 M` (c4) |
| `PTS5 Men` | `PTS5 M` (c1) — le seul cas 1-pour-1, celui que le sondage citait |

Aucun appariement de libellés ne peut réconcilier une fusion (`PTS2 Men` +
`PTS3 Men` → `PTS2-3 M`) ni un éclatement (`PTVI Men` → deux contests). L'étape
(A) telle qu'énoncée est **structurellement impossible**.

## 2. La vraie réconciliation : joindre par **dossard**, pas par libellé

Le contest est **explicite** dans les listes publiées (`TabConfig.Lists`, §3 du
sondage). Les listes publiées font donc **autorité** pour l'association
`dossard → contest`. Une ligne `hidden` n'a pas besoin qu'on interprète son
libellé de groupe : il suffit de retrouver **par dossard** à quel contest publié
elle appartient. Le libellé sort du chemin de jointure.

**Mesure de validation (406211, 13 contests, apex) :**

- 42 dossards publiés, **tous uniques** — aucun dossard réutilisé entre contests
  (le verrou #21 ne joue pas ici).
- 33 dossards dans le classement `hidden`, **tous** présents dans une liste
  publiée, chacun résolu vers **exactement un** contest.
- La granularité se résout d'elle-même : les dossards de `PTS2 Men`+`PTS3 Men`
  tombent tous dans `PTS2-3 M` ; ceux de `PTVI Men` dans `PTVI2-3 M` ; ceux de
  `PTS5 Men` dans `PTS5 M`.

La jointure par dossard est **exacte**, pas heuristique — c'est ce qui la rend
défendable là où l'appariement de libellés ne l'était pas.

## 3. L'élargissement est un **enrichissement**, jamais une création

C'est le cœur du design, et la garde qui rend (B) sûr.

**Les listes `hidden` n'introduisent ni participant ni contest.** Elles
**enrichissent** un participant déjà établi par une liste publiée, apparié par
dossard, avec :

1. ses **splits**, si la ligne publiée n'en portait aucun ;
2. les **champs scalaires laissés vides** (`total_time`, `club`, `category`,
   `gender`) — le publié reste l'autorité, le `hidden` ne comble que les trous.

### 3.1 Pourquoi l'enrichissement-seul neutralise les pièges par construction

Le sondage recense trois formes de listes `hidden` toxiques si on les traitait
comme sources de participants. Toutes deviennent **inertes** sous
enrichissement-seul, sans qu'on ait à les reconnaître ni à les filtrer par leur
`Name` (banni comme qualifiant, §3) :

| Forme `hidden` mesurée | Pourquoi inerte |
| --- | --- |
| `Concurrents\|Liste des Inscrits` (410891, 411749) | aucune cellule de durée → n'enrichit rien ; ses dossards inscrits-seuls ne sont dans aucune ligne publiée à enrichir |
| colonnes de split présentes mais **vides** (411749) | aucune valeur durée → rien à unir |
| classement `hidden` Contest=0 **redondant** (410891, 517 lignes, mêmes colonnes que le publié, **sans split**) | aucune colonne de segment → rien |

### 3.2 Gain concret mesuré

- **406211** : le classement `hidden` `01-Classements\|Classement général`
  (Contest=0) porte les colonnes `Swim/T1/Bike/T2/Run` (expressions
  `if([STATUS]=2;"";[Natation])`…), renseignées en durées (`10:27`, `00:50`,
  `32:13`…). L'enrichissement ajoute **5 splits × 33 finishers**. Ligne de base
  actuelle : 0 segment (les 13 listes publiées n'ont aucune colonne de split).
- **410891** : les splits réels (`10KMS`/`20KMS`) sont dans les listes `inter`
  (`hidden`, Contest 1/2), **mais au format `'2:05:29 (2)'`** (rang sans point).
  `_strip_rank_suffix` (strict, point exigé, §12.2) les laisse intacts,
  `_RE_DUREE` les rejette → **B est inerte ici, et inoffensif**. Les débloquer
  est l'objet du second verrou (C), hors périmètre — cf. §6.

## 4. Architecture

Le flux de `scrape_event_all` passe de « une passe sur les listes publiées » à
**trois temps**, sans toucher au reste du module :

1. **Spécifications.** `_iter_list_specs` continue de rendre les listes publiées
   (non-`hidden`). Une nouvelle `_iter_hidden_list_specs(config)` rend les listes
   `hidden` (toutes, indépendamment du `Name` ou du `Contest` — cf. décision de
   fetch, §5).
2. **Phase publiée (inchangée).** On récupère, qualifie et fusionne les listes
   publiées exactement comme aujourd'hui (`fusion: dict[(libellé, dossard)]`,
   `_prefer`/`_richness`, repli `Contest="0"` par `_groupes_zero_fiables`,
   collision #65). À l'issue, on construit l'**index d'autorité**
   `dossard → [clés de fusion publiées]` à partir de `fusion`.
3. **Phase d'enrichissement (nouvelle).** Pour chaque ligne de chaque liste
   `hidden` :
   - si son dossard mappe **exactement une** clé publiée → on enrichit le
     `ScrapedResult` de cette clé (`_enrichir`, §4.1) ;
   - si le dossard mappe **plusieurs** clés (dossard réutilisé entre contests,
     verrou #21) → enrichissement **ignoré** + `logger.warning` : la jointure est
     ambiguë, on ne devine pas ;
   - si le dossard n'est dans **aucune** clé publiée → ignoré (jamais de
     participant fantôme). `logger.debug`, car c'est le cas nominal des inscrits.

### 4.1 `_enrichir(existant, apport)`

Fonction pure, distincte de `_prefer` (qui reste l'arbitre **intra-publié**) :

- **Splits** : `existant.segments = existant.segments or apport.segments`. On ne
  fusionne pas deux listes partielles de segments — on ne prend l'apport que si
  l'existant n'en avait aucun. (Aucune épreuve du panel n'expose deux sources de
  splits sur un même dossard ; le faire serait une inférence non mesurée.)
- **Scalaires** : pour chaque champ de `(total_time, club, category, gender)`,
  `existant.x = existant.x or apport.x`. Remplit un trou, n'écrase jamais.
- **Rien d'autre** : `bib`, `event_*`, rangs, statut, nom/prénom du publié restent
  intouchés. Un enrichissement ne peut pas dégrader l'identité ni le classement
  déjà établis.

La qualification des cellules `hidden` (pelage, rôle, `_RE_DUREE` sur les
segments, `_strip_rank_suffix` strict) réutilise **telle quelle** la machinerie
existante : l'apport est produit par `_build_result` sur la ligne `hidden`,
exactement comme une ligne publiée. Seule la **fusion** change (enrichir au lieu
d'arbitrer), et seulement pour les lignes `hidden`.

### 4.2 Le libellé de la ligne `hidden` n'est jamais consulté

C'est le pendant du §2 : puisque la clé cible vient de l'index d'autorité
(dossard → clé publiée), on ne calcule ni ne lit le libellé de groupe de la ligne
`hidden`, ni son `Contest`. On court-circuite donc entièrement `_iter_groups` /
`_groupes_zero_fiables` pour les listes `hidden` : leurs lignes ne sont pas
qualifiées, elles sont **rattachées**. `_iter_groups` reste néanmoins appelé sur
elles pour une seule chose — le **statut** de groupe (`Abandons`…), qui, lui, peut
compléter un scalaire vide côté publié. (Cas non observé au panel ; garde de
robustesse, testée comme telle.)

## 5. Décision de fetch : **toutes** les listes `hidden`

Les colonnes d'une liste ne sont connues qu'**après** téléchargement (la config
ne les expose pas). On ne peut donc pas savoir *avant* fetch si une liste
`hidden` porte des splits. Trois options pesées :

- **Toutes les `hidden`** (retenu) — robuste, indépendant du `Name`.
  L'enrichissement-seul rend inertes les listes sans apport (§3.1).
- *Sauter les `Inscrits`* — économiserait des requêtes mais s'appuie sur un motif
  de `Name`, fragile et déconseillé (§3 du sondage : le `Name` n'est jamais un
  qualifiant).
- *Seulement Contest=0* — manquerait les splits `inter` du 410891 (Contest 1/2).
  Non général, écarté.

**Coût réseau assumé.** Le nombre de requêtes `list` passe de `len(publiées)` à
`len(publiées) + len(hidden)`. Mesuré : 406211 +2, 410891 +9, 411749 +10. Une
grosse liste redondante est téléchargée pour rien (410891 hidden_c0 = 77 Ko).
C'est un coût réel sur un `rescrape-db` de masse, documenté ici comme
tradeoff ; une optimisation ultérieure (borne, cache de colonnes) reste possible
mais n'est pas instruite.

## 6. Hors périmètre, explicitement

- **Verrou C (rang sans point, `'2:05:29 (2)'`, 410891)** reste **différé** : le
  §12.2 a arbitré *contre* la règle permissive (elle mutile `'TCN (1)'` et
  fusionne `'TCN (1)'`/`'TCN (2)'`). Rouvrir ce compromis mérite son propre
  ticket. B est inerte sur 410891 jusqu'à C ; il ne le **casse pas**.
- **Introduire des participants depuis une liste `hidden`** : jamais. Un finisher
  présent *uniquement* dans une liste `hidden` (aucune ligne publiée) n'est pas
  récupéré. **Non observé au panel** (toutes les épreuves sondées exposent leurs
  finishers dans au moins une liste publiée) ; angle mort assumé et consigné.

## 7. Angles morts (à consigner dans le sondage)

1. **Verrou #21 non exercé.** Aucune épreuve du panel ne réutilise un dossard
   entre contests. La branche « dossard ambigu → ignorer + warning » n'est
   couverte que par test unitaire, pas par donnée réelle.
2. **Fusion de deux sources de splits.** `_enrichir` ne prend l'apport que si
   l'existant n'a aucun segment. Le cas « publié partiel + hidden complémentaire »
   n'est ni observé ni géré (on garderait le publié partiel). Inférence évitée.
3. **Finisher hidden-seul non récupéré** (cf. §6).
4. **Le remplissage de scalaires depuis `hidden`** n'est exercé, sur le panel,
   par aucune épreuve où le publié manque un scalaire que le `hidden` porte
   (406211 publié a déjà nom+temps+sexe ; son `hidden` n'a pas de club). La
   branche existe pour l'inconnu, bornée par « remplir un vide, jamais écraser ».

## 8. Fixtures et tests

**Fixtures versionnées** (comble le trou §13.11 : aucune sonde n'était
versionnée). On verse les payloads réels capturés le 2026-07-23 sous
`tests/fixtures/raceresult/` :

- `406211_config.json`, `406211_hidden_classement.json`,
  `406211_pub_contest1.json` (au moins) — le cas nominal d'enrichissement.
- `410891_config.json`, `410891_hidden_c0.json` (redondant, sans split),
  `410891_inter_c1.json` (splits au format `(2)`), `410891_inscrits_c1.json` —
  les trois formes inertes + le verrou C.
- `411749_config.json` — colonnes de split `hidden` vides.

**Tests unitaires (TDD, sans réseau)** — pyramide, tests d'abord :

- `_iter_hidden_list_specs` rend bien les listes `hidden` (et rien d'autre).
- Index d'autorité `dossard → clé` : unique, multiple (→ ambigu), absent.
- `_enrichir` : union de splits seulement si l'existant est vide ; remplissage de
  scalaire vide ; non-écrasement d'un scalaire renseigné ; identité/rang
  intouchés.
- `scrape_event_all` sur fixture 406211 : 33 finishers gagnent 5 splits, aucun
  participant ni contest ajouté, les 42 lignes restent 42.
- **Non-régression des pièges** : sur fixtures 410891/411749, l'enrichissement
  n'ajoute aucun split (format `(2)` rejeté, colonnes vides, redondance), aucun
  participant fantôme, aucune bascule « en cours ».
- Verrou #21 synthétique : deux contests publiés partageant un dossard → ligne
  `hidden` de ce dossard **ignorée** + warning.

**Test d'intégration** (`@pytest.mark.integration`, réseau réel, ~3 s de délai) :
un scrape live de 406211 confirme les 33×5 splits — épinglé mais isolé du CI par
défaut.

## 9. Impact documentaire

- **Sondage §4.2** : amender pour refléter que l'écart est de **partition**, pas
  de graphie, et que la réconciliation retenue est la jointure par dossard (ce
  document). Ne pas laisser lire « réconcilier les libellés » comme la voie.
- **`AGENTS.md`** : la note sur l'élargissement `hidden` « différé derrière la
  réconciliation des libellés de contest » devient « réalisé par jointure sur
  dossard (#60), enrichissement-seul ». Mentionner le coût réseau et que le
  verrou C (410891) reste ouvert.
