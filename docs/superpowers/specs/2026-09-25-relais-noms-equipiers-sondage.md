# Sondage : les noms d'équipe de relais qui nomment leurs équipiers (#895)

**Date** : 2026-09-25 · **Issue** : #895 (sous-issue de #889, mécanisme d'attribution
livré par #997) · **Bases sondées** : `backend/triathlon.db` (dev, 11 629
participations dont **1 041 de relais**), fixtures de `backend/tests/fixtures`, code
des scrapers à `f6549e3a`.

Ce document est un **sondage** : il consigne ce qui a été mesuré, et il **prime** sur le
design, la spec et le plan de #895. Toute divergence se tranche en re-sondant.

## Méthode

- **Code** : lecture de chaque scraper qui pose `is_relay`, pour savoir quel champ source
  devient `athlete_name` / `athlete_firstname` et si `split_athlete_name`
  (`backend/app/scrapers/utils.py:149`) est appelé sur une ligne de relais.
- **Fixtures** : extraction des lignes de relais de chaque fixture, par les parseurs du
  scraper quand la donnée est encodée (data block Klikego, snapshot Chronoplace).
- **Base dev** : lecture seule (`mode=ro`) de `athletes.nom | athletes.prenom` joints aux
  participations, le fournisseur pris sur la `course_sources` active. Relais =
  `courses.is_relay` ; les deux drapeaux concordent sur les 11 629 lignes (1 041 à
  `(1, 1)`, 10 588 à `(0, 0)`).
- Aucun accès réseau, aucune base distante. Scripts `oktime.py`, `fx.py`, `kl.py`,
  `db.py`, `db2.py`, `db3.py` au scratchpad de la session ; ils lisent la donnée, pas
  l'implémentation.
- `team_name` vaut `NULL` sur les 1 041 relais de dev : aucun import ne le renseigne
  (`ScrapedResult.team_name` est « toujours vide côté import », `base.py:49`), seul
  `set_teammates` (`services/admin_actions.py:933`) le pose. La table
  `participation_teammates` n'existe pas encore dans la base dev (migration #997 non
  appliquée) : aucune attribution n'y est mesurable.

## Lecture d'une ligne de relais, par fournisseur

| Fournisseur | `is_relay` posé où | Champ source du nom | Relais : découpé ? | Réf. |
| --- | --- | --- | --- | --- |
| oktime | par **course** : titre `relais\|equipe\|duo\|team` ou majorité stricte de noms à `/` | `nom` | **Non** : nom entier, prénom vide, si course relais **ou** `/` dans le nom | `oktime.py:207-231`, `:266-268`, `:614` |
| raceresult | par ligne, sur le libellé du contest (`relais`, `relay`, `equipe`) | cellule du rôle « nom » | **Non** si `&` dans la valeur ou colonne `NomRelais`/`NomEquipe`/`AfficherNoms` non conditionnelle ; **sinon `split_athlete_name`** (un `/` est coupé) | `raceresult.py:934-957`, `:1029-1036`, `:1083-1085` |
| chronoweb | par épreuve, libellé `relais\|duo\|team` | colonne Nom | **Non** : nom entier, prénom vide | `chronoweb.py:127`, `:180-182`, `:405` |
| sporthive | par course, intitulé `relais\|relay\|equipe\|team\|duo` | `name` | **Non** : nom entier, prénom vide | `sporthive.py:374-377`, `:466` |
| timepulse | par ligne : parcours `relais` ou catégorie `EQX/EQM/EQF` | `n` (via `full_name`) | **Oui**, `split_athlete_name` inconditionnel | `timepulse.py:125-134`, `:391`, `:397` |
| wiclax | par ligne : parcours `p` contient `relais`/`relay` | `Name`/`FirstName`, sinon `n` | **Oui** (`split_athlete_name`) quand seul `n` existe | `wiclax.py:83`, `:102-111` |
| klikego | par heat (`heat_is_relay`) | champ `nom` du data block (ou cellule `td.truncate` en recherche) | **Oui**, `_split_name` local : préfixe majuscule = nom | `klikego_platform.py:184-190`, `:244`, `:465-477` ; `klikego.py:314-327` |
| breizhchrono | par heat : `heat_is_relay` + slug finissant par `---` | idem Klikego (moteur partagé) | **Oui**, même `_split_name` | `breizhchrono.py:184-195`, `:211`, `:241` |
| chronoplace | `isTeam` du snapshot ou catégorie `relais\|duo\|equipe` | colonne `nom` | **Oui**, `split_athlete_name` (limite verrouillée par test) | `chronoplace.py:429`, `:449` ; `test_chronoplace.py:636-646` |
| t2area | slug d'épreuve `eq\|relais\|duo` (non vérifié sur données réelles) | colonne `nom` | **Oui**, `split_athlete_name` | `t2area.py:248-251`, `:301`, `:322` |
| prolivesport | `categoryRef == "R"` ou `category == "relay"` | `lastname` / `firstname` séparés | Non (champs séparés, nom d'équipe dans `lastname`) | `prolivesport.py:156-176` |
| competitor | `_wtc_teamresult_value` non nul | `lastname`/`firstname`, repli `fullname` découpé | Non en nominal | `competitor.py:319-351` |
| runnerbreizh | nom d'épreuve ou catégorie d'équipe | cellule 0 | **Déjà une ligne par équipier** (hors sujet) | `runnerbreizh.py:215`, `:258-286` |
| sportinnovation | aucun `is_relay` posé | `lastName`/`firstName` | sans objet | `sportinnovation.py:205-217`, `:384-385` |

Conséquence directe : la forme stockée d'un même « DUPONT Jean / MARTIN Paul » dépend du
fournisseur. Entier en `nom` (oktime, chronoweb, sporthive, raceresult avec `&`), coupé
entre `nom` et `prenom` au premier jeton non majuscule (timepulse, klikego,
breizhchrono, chronoplace, wiclax). Un découpage par équipier doit donc partir de la
**valeur brute** du scraper, avant `split_athlete_name` / `_split_name`, pas de la
paire stockée.

## Mesures sur la base dev (1 041 relais)

| Fournisseur | Relais | Épreuves | Formes |
| --- | --- | --- | --- |
| breizhchrono | 675 | 6 | 434 « NOM D'ÉQUIPE \| Prénom et Prénom » exacts, 37 avec `&`, 2 avec `/`, 168 sans prénom, 10 autres |
| klikego | 230 | 10 | 168 équipiers nommés `/`, 54 groupes suffixés « . », 3 `&`, 3 `ET`, 1 masqué, 1 isolé |
| wiclax | 98 | 7 | 80 sans prénom, 11 coupes parasites, 4 `ET`, 3 `&` : **tous des groupes** |
| timepulse | 38 | 1 | 36 listes parallèles `/`, 2 initiales seules |
| oktime, raceresult, chronoweb, sporthive, chronoplace, t2area, prolivesport, competitor | 0 | 0 | aucun relais en dev |

### timepulse (38) : listes parallèles, découpables

Brut `NOM1/NOM2 Prénom1/Prénom2` ; `split_athlete_name` range la liste des noms en
`nom` et celle des prénoms en `prenom`. Stocké :

- `CANNIOU/OLIVIER | Cedric/Leclerc`
- `HUREAU /HUREAU/PERDREAU | Régis /Marianne/Jean-Sebastien`
- `PINSON/ROCHEFORT-CUNIN | Eric/Emmanuel`
- `BLOT/PARIS/CRONIER | Guillaume/Alex/Jean Philippe`, `QUILLET/BRILLANT CAMPBELL/ROUSSEAU | …`
- `S. D. | ` et `R. C. | ` (initiales, catégories EQX/EQF)

Les **36 listes ont la même longueur des deux côtés** (11 duos, 25 trios) : l'appariement
position à position est mécanique. Pièges mesurés : espaces autour de `/` irréguliers
(9 lignes : `HUREAU /HUREAU`, `Mathys /Clément`), noms composés à tiret ou espace dans
un élément (`ROCHEFORT-CUNIN`, `BRILLANT CAMPBELL`, `DI PALO`, `VI VAN CAN`), 11 équipes
familiales à nom répété (`LEGEARD/LEGEARD/LEGEARD`). Une ligne suspecte côté source :
`CANNIOU/OLIVIER | Cedric/Leclerc` donnerait l'équipier « OLIVIER Leclerc », très
probablement « Olivier LECLERC » inversé. 12 des 97 équipiers ont déjà une fiche
individuelle de même (nom, prénom).

### klikego (230) : `/` en tout majuscules, suffixe « . »

Brut `NOM PRÉNOM / NOM PRÉNOM .` ; `_split_name` coupe au premier jeton non
majuscule, ici le `/`. Stocké :

- `MASSONNEAU PIERRE | / BESANCON FABIEN .` (forme dominante, SwimRun Côte Beauté 2025)
- `DAUGUET PIERRE E. | / BELMONTE ALEXANDRE .`
- `LE BRAS LUC | / LE PAGE GUULLAUME .`, `BLOT JEAN BAPTISTE | / PHELIPOT CAROLLE .`,
  `GUILLET LOUISE | / GUILLET PONDAVEN CAMILLE .`, `BILLAULT PAUL | / MORIN BILLAULT AURELIE AURELIE .`

Sur 168 lignes (tous en duo, aucune minuscule), **144 ont deux jetons par équipier**
(découpables : 1er = nom, 2e = prénom) et **24 ont au moins un équipier à 3 ou 4
jetons**, où la frontière nom/prénom est indécidable par la casse (`LE BRAS LUC` contre
`BLOT JEAN BAPTISTE`). L'ordre NOM PRÉNOM est corroboré par les fiches existantes : 13
équipiers à deux jetons retrouvent une fiche individuelle en lisant (nom, prénom), 1 seul
en lisant l'inverse. Le suffixe ` .` est un artefact source (il apparaît aussi seul en
prénom des groupes) et doit être retiré avant tout découpage.

Groupes du même fournisseur, à **ne pas** découper : `TEAM GV | .`, `LES REUILLOIS | .`,
`PARKER | 1 .`, `TIC | & TAC .`, `ZEN | & ZINZIN .`, `BEN | & FANNY .`,
`PATOU ET SANDRINE | .`, `FRERE ET SUEUR | .`, `TOTO LESCARGOT ET MANUE LA TORTUE | .`.
Aucun `&` ni `ET` klikego ne relie deux noms complets : ce sont des prénoms ou des
surnoms.

### breizhchrono (675) : nom d'équipe suivi des seuls prénoms

Brut `NOM D'ÉQUIPE Prénom et Prénom` ; `_split_name` met le nom d'équipe en `nom`.
Stocké :

- `LES BARBAPAPAS | Alex et Margot`, `DARU SQUAD | Vincent et Antoine` (434 formes exactes)
- `RONAN | & VALERIE Ronan et Valerie`, `GILLES | & ALFRED Gilles et Alfred`
- `DAMIEN/FRANCOIS | Francois et Benjamin`, `ECN | / USCAL Sarah et Francois`
- `LES | 3 P Laura et Romain`, `NAGEURS DU | 92 Tebiz et Mickael`, `COUSITRI | Charlie et`,
  `BERGEROUX | Titouan Et Christophe`
- 168 sans prénom : `LES COPAINS`, `TEAM SAVORNIN`, `ROLET PERE FILS`

Aucune ligne ne porte un **nom de famille** par équipier : ce sont des **prénoms
seuls**. Les découper créerait des fiches « Alex », « Margot » sans nom, soit des
identités fausses. Seul `BERGEROUX | Titouan Et Christophe` suggère un nom de famille
commun, lecture non généralisable.

### wiclax (98) : groupes uniquement

`CHOUQUETTE`, `LES COPAINS D’ABORD`, `MYMY&TINTIN`, `OGGY ET LES CAFARDES`,
`PIC ET PIC ET COLEGRAM`, `LE PICHON, LA DRAGODINDE ET LE TOFU`,
`LE VIEUX PLOUF | & LES ROCKETS`, `LES | 3 PAQUETS PERDUS`, `LAIT | 45`, `LES TRI PINTES | 🍻`.
Aucun équipier nommé : `&` et `ET` y relient des surnoms ou des mots, jamais des personnes
identifiables.

## Fixtures

| Fournisseur | Fixture | Valeur brute | Classe |
| --- | --- | --- | --- |
| oktime | `oktime_lacanau_48555.json`, course « Relais L & Duo » (59698) | `GUILLON RÉMI / CHARPENTIER EMMANUEL` (club `TEAM TCC`) | équipiers nommés, **ordre ambigu** (tout majuscules, alors que l'individuel oktime est « Prénom NOM ») |
| oktime | tests `test_oktime.py:267-315` (synthétiques) | `A DUPONT / B MARTIN`, `C DURAND / D PETIT` | équipiers nommés « Prénom NOM » |
| raceresult | `raceresult/410891_*`, `411749_config.json`, `raceresult_config_foulee.json` | aucune ligne d'équipe : trails et une course à pied ; « Relais » n'y figure que dans des **noms de listes** (`Relais\|Classement général inter`, `Classement général_Equipe avec temps Relais`) ; `Team Sport 85` est un club | **aucun relais nommé** |
| raceresult | tests `test_raceresult.py:2375-2471` (synthétiques, d'après 403144) | `GUILLAUME & ANTHONY` | prénoms seuls |
| chronoweb | `chronoweb/event_aquathlon_relais.html` (Verrerie 2025, 16 lignes, 2 équipes × 8 points) | `CREUSOTRI`, `FRATERIES POZZEBON/SKLADZIEN` | groupe ; **ambigu** (groupe + deux noms sans prénoms) |
| sporthive | `sporthive_relay.json` | `LA COUSINADE`, `LES TRIATHLETES DE ST GILLES`, `EQUIPE 460` | groupes |
| timepulse | aucune fixture fichier ; tests `test_timepulse.py:552-553` (d'après l'épreuve 3232) | `ROUXEL/ROUXEL Didier/Emma`, `CANNIOU/OLIVIER Cedric/Leclerc` | équipiers nommés, découpables |
| wiclax | `chronowest_red_ouf_reduit.clax` (parcours « S Duo ») | `LES PHELIPOPOV .`, `LES TITOUILLES .` | groupes |
| chronoplace | `chronoplace_epreuve_566.html` | `MENARDAIS FERDINAND / COMPAIN LENA` (Relais Mixte), `LE BOZEC HENRI / BABINET SYLVAIN` (Duo Masculin) | équipiers nommés ; 2e **ambigu** (`LE BOZEC HENRI`) |
| chronoplace | `chronoplace_epreuve_493.html` (24 h VTT, `isTeam`) | `CREPHAISSON`, `LA ROUE LA VRAIE` | groupes |
| klikego / breizhchrono | `klikego_datablock_page0.html` (50 lignes), `breizhchrono_live_*`, `klikego/*` | aucune ligne de relais (heat individuel ; `breizhchrono_live_classements.html` ne liste que le slug `triathlon-distance-olympique---relais`) | **aucun relais nommé** |
| runnerbreizh | `runnerbreizh_duo.html` | `THOMAS Matthieu` et `COGREL Alban`, rang `1 /31` partagé | une ligne par équipier (hors sujet) |
| competitor | `competitor_results_*.json` | aucune ligne `_wtc_teamresult_value` | sans relais |

Mesures antérieures sur panel réel, à reprendre sans les re-mesurer ici : oktime,
**347 participations** de forme `NOM PRÉNOM / NOM PRÉNOM` sur 12 644
(`2026-07-26-oktime-scraper-design.md` §4.1) ; chronoweb, 707 équipes au nom d'équipe
(`LES BRAS CASSÉS`, `TRIPOTES TEAM GOLFECH RELAIS1`) dont 52 mutilées par le découpage
individuel avant correctif (`2026-07-29-chronoweb-sondage.md`) ; raceresult, 19
identités mutilées sur 17 épreuves (`GUILLAUME & ANTHONY`, `Les Inconnus Associés`,
`2026-07-19-raceresult-api-sondage.md` §12.3).

## Classement des formes

| Classe | Formes mesurées | Volume dev |
| --- | --- | --- |
| **Découpable sans ambiguïté** | timepulse listes parallèles `NOMS/… Prénoms/…` de même longueur ; klikego `NOM PRÉNOM / NOM PRÉNOM .` à deux jetons par équipier | 36 + 144 = **180** |
| **Équipiers nommés, frontière nom/prénom ambiguë** | klikego à 3+ jetons (`LE BRAS LUC`), oktime tout majuscules (`GUILLON RÉMI`), chronoplace `LE BOZEC HENRI` | 24 en dev ; oktime 347 sur le panel de son design |
| **Prénoms seuls** | breizhchrono `ÉQUIPE \| Prénom et Prénom` (497), klikego `BEN & FANNY` (1) ; raceresult `GUILLAUME & ANTHONY` en test | 498 |
| **Nom de groupe** | `TEAM GV`, `LES COPAINS`, `OGGY ET LES CAFARDES`, `MYMY&TINTIN`, `TIC & TAC` ; en fixture `LA COUSINADE`, `CREUSOTRI` | 335 (breizhchrono 178, klikego 59, wiclax 98) |
| **Ambigu autre** | initiales `S. D.`, `R. C.`, masqué `XXX XXX`, équipier isolé `SABOURIN Maxime` ; en fixture `FRATERIES POZZEBON/SKLADZIEN` (noms sans prénoms) | 4 |

Deux constats pour la règle de découpage :

1. **`&`, `et`, `ET` ne séparent jamais deux noms complets** dans les données mesurées :
   sur 43 `&` et 502 `et/ET` de relais, aucun ne relie deux personnes nommées en
   entier. Seul `/` le fait (timepulse, klikego, oktime, chronoplace). L'exemple
   « A & B » de l'issue n'a pas de réalisation mesurée sous forme de noms complets.
2. Un `/` n'est pas suffisant seul : `DAMIEN/FRANCOIS`, `ECN / USCAL Sarah et Francois`
   et `FRATERIES POZZEBON/SKLADZIEN` portent un `/` sans équipiers identifiables. Le
   critère mesuré est « chaque segment porte au moins un nom et un prénom ».

## Risques hors relais

- **Tiret** : 303 participations non relais ont un `-` dans le nom ou le prénom
  (breizhchrono 221, sportinnovation 47, klikego 21, timepulse 14) :
  `BODENON-CHARLET Manon`, `COUPÉ Jean-François`, `MUSY-HASPEL Mathieu`. Et en relais
  même, un élément de liste contient un tiret (`ROCHEFORT-CUNIN`, `Jean-Sebastien`) :
  le tiret n'est jamais un séparateur d'équipiers.
- **`/`, `&`, `et` hors relais** : aucune personne légitime en dev. Les deux seuls cas
  sont des **binômes sur une épreuve individuelle** : `CHAIGNEAU BENJAMIN | / LENOIR-LEDOUX
  CHRISTELLE .` (klikego, « SwimRun Côte Beauté 2025 · Format M individuel ») et
  `LES PATATALO | Gaelle et Laure` (breizhchrono, « Swimrun Court Solo »). La règle « jamais
  hors relais » les laisse entiers, ce qui est le comportement voulu par l'issue.
  L'affirmation de #63 selon laquelle des noms de personne portent `/` n'a **aucune
  occurrence mesurée** en dev ; elle reste une précaution.
- **Tests existants de noms de personne** : tirets seulement, aucun `/`, `&` ni `et` dans
  un nom de personne non relais : `Marie-Claire LE GALL`, `Jean DE LA TOUR`
  (`test_scrapers_utils.py:80-84`), `DUBOIS-HERRY`, `Anne-Sophie`
  (`test_athlete_repository.py:359`, `:603`), `Pierre-arnaud`
  (`test_sportinnovation.py:290`). Les tests d'équipe portent déjà des relais nommés :
  `DUPONT Jean / MARTIN Paul`, `DUPONT JEAN / MARTIN | PAUL` (forme timepulse coupée),
  `DUPONT Jéan & MARTIN Paul` (`test_import_service.py:1679-1737`).
- **Interaction avec #997** : un relais attribué sans dossard se ré-apparie au rescrape par
  `team_name` normalisé (`import_service.py:471-473`, `:589-592`). Changer la forme du
  nom brut entre deux scrapes changerait la clé.

## Fournisseurs sans données mesurables

- **raceresult** : aucun relais en dev, aucune ligne d'équipe dans les fixtures citées
  (410891, 411749, foulee). Seuls existent des cas synthétiques de test
  (`GUILLAUME & ANTHONY`) et les 19 identités du sondage de juillet. **Aucune forme
  « équipiers nommés en entier » n'est mesurée pour raceresult.**
- **chronoweb** : aucun relais en dev ; la fixture ne porte que `CREUSOTRI` (groupe) et
  `FRATERIES POZZEBON/SKLADZIEN` (noms sans prénoms). **Aucun équipier nommé en entier
  mesuré.**
- **oktime** : aucun relais en dev ; une seule ligne en fixture
  (`GUILLON RÉMI / CHARPENTIER EMMANUEL`) et le chiffre de 347 du design, sans
  échantillon de valeurs pour trancher l'ordre nom/prénom.
- **sporthive, t2area, competitor, prolivesport** : aucun relais nommé mesuré (groupes
  seuls pour sporthive, aucune ligne pour les autres).

Parmi les quatre fournisseurs exigés par l'issue, **seul timepulse** a des relais nommés
mesurables et découpables. Klikego (144 lignes découpables) et chronoplace (fixture 566)
sont les deux autres porteurs réels.

## Limites

- **La production n'est pas mesurée** : accès interdit dans ce sondage. Les volumes
  ci-dessus sont ceux de dev (72 épreuves) et de fixtures souvent réduites. L'exemple de
  l'issue (athlète 102324) n'a pas pu être observé.
- La base dev n'a pas la migration de #997 : aucun `participation_teammates` mesuré.
- Les chiffres de panels antérieurs (oktime 347, chronoweb 707/52, raceresult 19) sont
  repris de leurs documents, pas re-mesurés.
