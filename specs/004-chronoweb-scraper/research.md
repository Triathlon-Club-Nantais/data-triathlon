# Phase 0 — Recherche : scraper chronoweb.com

Toutes les décisions ci-dessous sont **mesurées**, pas supposées. La source des
mesures est le sondage (`docs/superpowers/specs/2026-07-29-chronoweb-sondage.md`)
et les relevés complémentaires faits le 29/07/2026 sur les mêmes pages.

## R1 — Bibliothèque et coût du parsing

**Décision** : `httpx` + `BeautifulSoup(html, "lxml")`, comme tous les scrapers
HTML du projet. Aucune dépendance nouvelle.

**Rationale** : mesuré sur la page la plus lourde du panel (Triathlon de Dijon
2026, 4 532 678 octets, 4 787 lignes) :

| Étape | Coût |
| --- | --- |
| Téléchargement | 1,09 s |
| `BeautifulSoup(..., "lxml")` | 1,20 s |
| Sélection + extraction des 4 787 lignes | 0,75 s |
| Empreinte mémoire (RSS) au pic | 144 Mo |

Soit ~3 s et 144 Mo pour le pire cas d'un catalogue de 222 événements — dans
l'enveloppe d'un import qui traite déjà des payloads comparables.

**Alternatives rejetées** :

- `lxml.html` + `cssselect` (parse 24× plus rapide : 0,05 s) — `cssselect`
  n'est pas dans les dépendances, et le gain est sans objet face à la seconde de
  téléchargement. Ajouter une dépendance pour 1,2 s sur l'import le plus lourd
  contredit YAGNI (principe VI).
- Streaming / parsing incrémental — inutile : 144 Mo est le pic mesuré, pas une
  extrapolation.

## R2 — Motifs de points de chronométrage → segments

**Décision** : table de correspondance sur la **suite ordonnée des libellés de
points** (Natation, Vélo, Course), avec repli sur le chemin générique.

Mesuré sur les 89 épreuves du panel :

| Motif | Épreuves | Traitement |
| --- | --- | --- |
| `Natation → Vélo → Course` | 43 | slots `swim` / `t1`* / `bike` / `t2`* / `run` |
| `Course` seul | 29 | slot `run` |
| `Natation → Course` | 10 | slots `swim` / `t1`* / `run` |
| `Course → Vélo → Course` | 4 | slots `swim` / `t1`* / `bike` / `t2`* / `run` (le gabarit duathlon les renomme `course1` / `course2`) |
| `Vélo` seul | 2 | slot `bike` |
| `N→C→N→C→N→C→N→C` | 1 | **liste de segments étiquetés** avec les libellés publiés, transitions* intercalées (nulles sur cette épreuve, donc absentes) |

\* transitions calculées, cf. R3 — sur tous les motifs, y compris le dernier.

**Rationale** : les slots positionnels sont ré-étiquetés par discipline en aval
(`services/mapping.build_splits`), ce qui donne un affichage identique à celui
des autres fournisseurs. Le motif, et non la discipline, décide du remplissage :
c'est lui qu'on observe. Le gabarit de discipline filtre ensuite les slots hors
sujet — un aquathlon ne publie pas de clé `bike` même si un slot vélo était
rempli par erreur.

**Vérifié** : chaque combinaison (motif, `event_type` classé) du panel produit un
jeu de clés cohérent, y compris les cas dégradés du classifieur
(« Les Géraldines » classé `triathlon` avec un seul point Course → clé `run`
seule ; « Challenge 1er Tour » classé `duathlon` avec un seul point Vélo → clé
`bike` seule).

**Alternative rejetée** : décider du remplissage à partir de l'`event_type`
plutôt que du motif. Elle casse dès que le classifieur se trompe (mesuré : 3
épreuves du panel), là où le motif reste juste.

## R3 — Transitions calculées

**Décision** : `transition[i] = cumul[i] − intervalle[i] − cumul[i−1]`, calculée
dès que les deux points encadrants existent pour le participant, **quel que soit
le motif** (clarification du 2026-07-30). Une valeur nulle n'est pas enregistrée
(le slot reste vide), une valeur négative ne peut pas se produire.

Deux destinations selon le chemin de sortie (R2) :

| Chemin | Destination de la transition |
| --- | --- |
| motif reconnu → slots | `t1_time` / `t2_time`, ré-étiquetés par `build_splits` |
| motif non reconnu → `segments` | entrée intercalée `("Changement", durée)` — le libellé de la fiche individuelle du site |

Sur le chemin `segments`, la répétition d'un libellé n'écrase rien :
`mapping.build_splits` suffixe les collisions en ` (N)` (`mapping.py:78-82`), et
le front colore un libellé libre via `sourceEntry` (`lib/utils/splits.ts`).
L'aquathlon relais à 8 points sort à **8** segments : re-sondé le 2026-07-30, ses
7 écarts sont **nuls** sur les 14 équipes (points contigus), et un temps mort nul
n'est pas enregistré. La règle d'intercalage vaut toujours — faute de motif non
reconnu à temps mort dans le panel, elle est couverte par un cas construit.

**Rationale** : vérifié sur 17 497 écarts — jamais négatif ; et égal au
caractère près au « Changement » que publie la fiche individuelle (contrôles sur
Oléron 2024 / dossards 360 et 347, deux transitions chacun). Les 1 440 écarts
supérieurs à 10 minutes sont concentrés sur Oléron et Altriman, dont les
transitions sont réellement longues.

**Alternative rejetée** : lire les transitions sur la fiche individuelle — une
requête par participant (jusqu'à 1 622 par événement), pour une page cassée à la
source sur les épreuves mono-point.

## R4 — Ville de l'événement

**Décision** : une requête d'appoint sur `/resultats.php`, dont on lit la ligne
du catalogue portant `resultats_evenement.php?event=<id>` et sa cellule
`div.table-cell.location`. Résultat rangé dans `raw_data["city"]`. Tout échec
(HTTP, absence de la ligne) est **journalisé et ignoré** : l'import se poursuit
sans ville.

**Rationale** : la ville n'existe nulle part sur la page de résultats. Le
catalogue pèse 170 Ko (4 % du poids d'un gros événement) et son paramètre
`annee` est ignoré côté serveur : une seule requête donne les 222 événements.
Même usage que `raw_data["city"]` chez runnerbreizh, dont la commune est plus
juste que celle déduite du nom d'épreuve.

**Pas de mémoïsation** (clarification du 2026-07-30) : la requête est refaite à
chaque import d'événement, le fournisseur reste sans état. `PROVIDERS` tient des
instances singleton de module (`registry.py:305`), donc un cache d'instance
serait un cache de processus, y compris entre tests — pour ~340 Ko économisés au
plus : le Sheet porte 5 URLs chronoweb distinctes, mais **2 événements**
seulement (323 et 347, cf. sondage § Les URLs réellement présentes dans le
Sheet). Même arbitrage que R1 : YAGNI (principe VI).

## R5 — Canonicalisation et refus d'URL

**Décision** : reconstruction par **allowlist** à partir du seul paramètre
`event` → `https://chronoweb.com/resultats_evenement.php?event=<id>`.

| Forme soumise | Traitement |
| --- | --- |
| `resultats_evenement.php?event=…&epreuve=…&cat=…&point=…` | canonicalisée (les paramètres d'affichage sont retirés) |
| `resultats_participant.php?event=…&epreuve=…&bib=…` | canonicalisée vers son événement |
| toute URL sans paramètre `event` (dont `/files/pdf/*.zip`) | **refusée** avec un message nommant la forme attendue |

**Rationale** : soustraire les paramètres connus un à un cesserait d'être juste
au prochain paramètre d'affichage ajouté par le site. Reconstruire depuis
`event` reste vrai par construction. Le refus couvre l'archive ZIP réellement
présente dans le Sheet.

**Portée** : la canonicalisation fixe le `source_url` des `ScrapedResult`, pas
`Course.source_url` — `import_service` y écrit l'URL soumise, donc deux graphies
d'un même événement le re-scrapent. Identique à runnerbreizh, hors périmètre.

## R6 — Détection des épreuves par équipes

**Décision** : le **libellé de l'épreuve** (`relais`, `duo`, `team`, sans
accent ni casse) marque l'épreuve comme relais. La catégorie n'est pas utilisée.

**Rationale** : mesuré — `MASC`, `FEM` et `MIXT` apparaissent aussi hors relais
(50 / 45 / 64 lignes), notamment sur des épreuves individuelles où ils servent
de catégorie « toutes classes ». Le libellé, lui, ne se trompe pas sur le panel :
les 6 épreuves de type équipe le déclarent (`S Relais`, `Triathlon M Relais`,
`Swinrun M duo`, `Aquathlon Team Relais`).

**Conséquence liée** : sur une épreuve ainsi marquée, le libellé de la colonne
Nom est enregistré entier comme nom, sans prénom (52 des 707 équipes du panel
sont mutilées par le découpage des individus).

## R7 — Genre déduit de la catégorie

**Décision** : règle en cascade, validée sur les **81** codes du panel :

1. `MIXT`, `DUOX`, `DUOM`, `DUOF` → aucun genre (le code décrit une équipe) ;
2. `MASC` → `M`, `FEM` → `F` ;
3. code commençant par `M`/`F` **suivi d'une lettre** → premier caractère
   (`MSE`, `FV1`, `MCA`) ;
4. sinon, dernier caractère s'il vaut `M`/`F` (`SEM`, `V1F`, `M0F`, `M1M`) ;
5. sinon → aucun genre.

**Rationale** : deux conventions cohabitent dans le même champ. La règle 3 doit
exiger une lettre en deuxième position, sinon `M0F` (femme master 0 FFA) serait
lue comme masculine — 36 codes féminins du panel passent par la règle 4.

## R8 — Erreurs et cas limites

| Situation | Comportement |
| --- | --- |
| Pas de nom d'événement dans la page (`h2.name` absent) | `ValueError` : identifiant d'événement inconnu |
| Nom présent, aucune épreuve avec tableau | liste vide, sans erreur (événement sans classement publié) |
| URL sans paramètre `event` | `ValueError` nommant la forme attendue |
| Ligne dont le nombre de cellules diffère de 9 | ligne ignorée, avertissement journalisé |
| Temps illisible | segment vide, la participation reste importée |
| Requête catalogue en échec | ville absente, import poursuivi |

**Rationale** : c'est la distinction déjà retenue pour runnerbreizh — une URL
fausse doit échouer bruyamment, une épreuve non encore publiée non. Les messages
destinés à l'opérateur sont en français (constitution, cas mixte des
`DomainError`).

## R9 — Stratégie de test sans réseau

**Décision** : fixtures HTML **réduites mais verbatim** sous
`backend/tests/fixtures/chronoweb/`, extraites des pages réellement téléchargées
(en-tête d'événement + sélecteur d'épreuves + quelques lignes par épreuve, sans
retoucher le markup). Le réseau est neutralisé par monkeypatch de `httpx.Client`,
comme dans `tests/test_klikego.py`.

**Rationale** : les pages réelles pèsent jusqu'à 4,5 Mo — inversables dans le
dépôt. Un extrait verbatim conserve les pièges structurels (rangs superposés,
lignes multiples par dossard, classes `hidden`) que du markup réécrit à la main
perdrait.

**Fixtures prévues** (une par cas structurel, toutes tirées du panel) :

| Fixture | Origine | Ce qu'elle couvre |
| --- | --- | --- |
| `event_triathlon.html` | Oléron 2024 (`event=323`) | 3 épreuves, motif `N→V→C`, un non-finisher, un participant à point intermédiaire manquant |
| `event_duathlon.html` | Toulouse 2024 (`event=296`) | motif `C→V→C`, épreuve relais, classements dérivés à point unique |
| `event_aquathlon_relais.html` | La Verrerie 2025 (`event=334`) | motif à 8 points → segments étiquetés, 8 entrées (temps morts nuls), libellés répétés |
| `event_mono_point.html` | ALEFPA Trail 2025 (`event=356`) | motif `C` seul, sans transition possible |
| `event_sans_classement.html` | Chalain 2015 (`event=146`) | nom présent, aucun tableau |
| `event_inconnu.html` | `event=99999` | « Aucun évènement trouvé avec cet ID » |
| `catalogue.html` | `/resultats.php` réduit | lecture de la commune |

**Tests réseau réel** : marqués `integration`, sur Oléron 2024 (effectifs
publiés connus : 3 épreuves, 854 participants).
