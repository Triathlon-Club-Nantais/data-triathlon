# Research : découper à l'import les relais qui nomment leurs équipiers (#895)

Source de terrain : `docs/superpowers/specs/2026-09-25-relais-noms-equipiers-sondage.md`
(prime sur ce document). Code lu à `f6549e3a` (epic/889-relais, #997 incluse).

## R1. Où découper : dans les scrapers ou à l'import ?

- **Decision** : à l'import, dans `_Persister` (`backend/app/services/import_service.py`),
  à partir de la valeur **reconstituée** `" ".join(athlete_name, athlete_firstname)`.
  La règle de découpage est une fonction pure, `split_relay_teammates`, dans
  `backend/app/scrapers/utils.py`, à côté de `split_athlete_name`.
- **Rationale** :
  - Tous les scrapers qui posent `is_relay` produisent soit le nom entier dans `nom`
    (oktime, chronoweb, sporthive, raceresult avec `&`), soit une coupe au premier
    jeton non majuscule (timepulse, klikego, breizhchrono, chronoplace, wiclax, t2area).
    Dans les deux cas, la concaténation `nom + " " + prénom` restitue la valeur publiée,
    au détail près des espaces. Un seul point d'application couvre les 14 fournisseurs
    sans toucher un scraper.
  - Le rescrape (FR-009) passe par le même `_Persister` : un découpage à l'import
    s'applique donc aussi aux relais déjà en base, sans chemin dédié.
  - La clé d'appariement sans dossard de #997 (`_team_key` de la même concaténation,
    `import_service.py:694`) reste la même d'un scrape à l'autre.
- **Seule exception à la restitution** : `split_athlete_name` en forme « Prénom NOM »
  (bloc majuscule en queue) réordonne la chaîne : « Jean DUPONT / Paul MARTIN » devient
  `nom="MARTIN"`, `prenom="Jean DUPONT / Paul"`, soit « MARTIN Jean DUPONT / Paul ».
  La règle R3 rejette cette forme (le segment « Paul » n'a pas de nom, le segment
  « MARTIN Jean DUPONT » a deux blocs majuscules) : aucune fausse personne, la ligne reste
  une fiche d'équipe comme aujourd'hui. Aucun relais de ce type n'est mesuré (raceresult
  sans relais nommé au sondage).
- **Alternatives considered** :
  - Un champ `ScrapedResult.teammates` rempli par chaque scraper : 8 scrapers à toucher,
    une règle dupliquée ou importée partout, et le rescrape d'une ligne déjà stockée
    n'en profite que si le scraper le remplit. Rejeté (Principe VI).
  - Remplir `ScrapedResult.team_name` avec la valeur brute dans chaque scraper : corrige
    le cas « Prénom NOM », qui n'a aucune occurrence mesurée, au prix de 8 scrapers
    modifiés. Rejeté tant qu'aucune donnée ne le justifie.

## R2. Quel séparateur ?

- **Decision** : `/` seul.
- **Rationale** : sondage, 43 `&` et 502 `et/ET` de relais, aucun ne relie deux noms
  complets ; tous les relais aux équipiers nommés en entier utilisent `/` (timepulse,
  klikego, oktime 347 lignes au panel de son design, chronoplace).
- **Alternatives considered** : `&`, `et`, `+` : ne produiraient que de fausses personnes
  sur les données mesurées (« TIC & TAC », « OGGY ET LES CAFARDES »).

## R3. Règle de découpage (tout ou rien par ligne)

- **Decision** : voir `contracts/relay-teammates-rule.md`. En bref :
  1. Jetons faits uniquement de `.` retirés (suffixe klikego), espaces normalisés.
     Sans `/` : pas de découpage.
  2. **Listes parallèles** (timepulse) : si `split_athlete_name` donne un bloc de noms et
     un bloc de prénoms qui contiennent tous deux `/`, on les coupe sur `/` et on les
     apparie position à position ; les deux listes doivent avoir la même longueur.
  3. **Segments** (klikego, oktime, chronoplace) : sinon on coupe la valeur sur `/`, et
     chaque segment doit donner un nom et un prénom :
     - casse mixte : un seul bloc majuscule, en tête ou en queue (nom), le reste est le
       prénom ;
     - tout en majuscules : exactement deux jetons, lus « NOM PRÉNOM » ;
     - sinon (un jeton, trois jetons ou plus en majuscules, aucune majuscule, `&`, `+`
       ou `et` présents) : la ligne entière est rejetée.
  4. Chaque nom et prénom porte au moins deux lettres (écarte les initiales « S. D. »,
     « E. »), 2 à 8 équipiers, aucun doublon (comparaison sans accents ni casse).
- **Rationale** : reproduit exactement le classement du sondage : 180 découpables
  (36 timepulse + 144 klikego), 24 klikego ambigus rejetés, prénoms seuls et groupes
  rejetés. Le tiret n'est jamais un séparateur (`ROCHEFORT-CUNIN`, `Jean-Sebastien`).
- **Lecture « NOM PRÉNOM » des segments tout majuscules** : corroborée sur klikego (13
  fiches existantes retrouvées dans ce sens, 1 dans l'autre), cohérente avec oktime
  (`GUILLON RÉMI`) et chronoplace (`MENARDAIS FERDINAND`). Risque résiduel : un
  fournisseur qui publierait « PRÉNOM NOM » en majuscules donnerait des équipiers au nom
  et au prénom inversés (pas de fausse personne, mais une fiche mal nommée). Aucune
  occurrence mesurée.
- **Alternatives considered** : convention d'ordre déclarée par fournisseur : sans
  objet tant qu'aucun fournisseur mesuré ne publie « PRÉNOM NOM » en majuscules
  (Principe VI).

## R4. Condition « relais »

- **Decision** : `scraped.is_relay` vrai. C'est lui qui fixe `Course.is_relay` (identité
  de course) et `Participation.is_relay`. Hors relais, `split_relay_teammates` n'est
  jamais appelée (FR-007).
- **Rationale** : les deux drapeaux concordent sur les 11 629 lignes de dev ; les binômes
  inscrits en individuel (`CHAIGNEAU BENJAMIN / LENOIR-LEDOUX CHRISTELLE`) restent
  entiers, comme voulu.

## R5. Identité des équipiers

- **Decision** : même résolution par lot que les autres lignes
  (`athlete_repository.get_by_identities_batch`, nom et prénom sans casse, date de
  naissance nulle), création par `create_batch` des manquants avec **nom et prénom
  seulement** (ni genre, ni club, ni date). Pas de synchronisation de club sur un
  équipier.
- **Rationale** : le club et la catégorie publiés sont ceux de l'équipe (souvent
  « TEAM TCC », catégorie mixte) ; les recopier sur chaque personne écraserait un club
  individuel exact. `set_teammates` (#894) crée lui aussi les équipiers par nom et
  prénom seuls (`athlete_repository.get_or_create(nom=…, prenom=…)`). Le club reste porté
  par la participation (`Participation.club`), seule source de `is_tcn`.
- **Écart assumé avec #894** : `set_teammates` compare les nouveaux équipiers sans
  accents pour détecter un doublon dans l'équipe ; la résolution par lot compare sans
  casse mais avec accents. Le doublon **dans une ligne** est rejeté sans accents par la
  règle (R3), la résolution vers une fiche existante suit l'import comme pour tout
  coureur.

## R6. Intégration dans `_Persister`

- **Decision** :
  - `add()` calcule `teammates = split_relay_teammates(...)` pour une ligne relais et le
    porte dans `_PendingResolution` (nouveau champ). Les chemins déjà en place de #997
    passent **avant** et restent inchangés : dossard apparié à un relais déjà composé,
    ou relais sans dossard retrouvé par nom d'équipe → `_upsert` seul (FR-009,
    idempotence ; une composition posée à la main n'est jamais retouchée).
  - `_resolve_pending()` : les paires d'identité à **chercher** incluent l'identité
    d'équipe (pour retrouver une fiche d'équipe existante) et les équipiers ; les paires
    à **créer** excluent l'identité d'équipe d'une ligne découpée.
  - Ligne découpée, trois cas :
    1. dossard apparié à un résultat sans composition (relais importé avant #895) :
       composition posée, porteur = premier équipier, `team_name` renseigné, ancienne
       fiche d'équipe candidate à la purge ;
    2. sans dossard, la fiche d'équipe existe et `_match_without_bib` la trouve : même
       traitement ;
    3. sinon : participation créée avec porteur = premier équipier, `team_name` et
       composition.
  - Garde FR-010 : si un équipier est déjà porteur ou équipier d'un **autre** résultat de
    la course, la ligne retombe sur le chemin non découpé, exactement comme aujourd'hui.
    Deux ensembles par course : les **ids** déjà présents (`self._participations[course_id]`
    et leurs compositions) et les **clés d'identité** (nom, prénom normalisés) réservées
    par les lignes composées de ce scrape. Les clés sont nécessaires parce qu'un équipier
    neuf n'a pas encore d'id quand la garde est décidée (avant `to_create`) : deux lignes
    du même lot qui partagent un équipier neuf ne seraient pas distinguées par les ids.
  - Purge : `athlete_repository.delete_orphans_among` sur les anciennes fiches d'équipe,
    une fois par lot, après un `flush` (la session n'a pas d'`autoflush`).
  - Ajouts de la revue de code :
    - les lignes à découper sont résolues **après** toutes les autres lignes de la
      course (`finalize`), pour que la garde FR-010 voie chaque coureur, quelle que
      soit sa tranche ;
    - une ligne sans dossard dont la fiche d'équipe porte plusieurs lignes sur la
      course, ou une ligne déjà reprise, n'est pas découpée : elle suit les crédits
      du chemin d'avant #895, sans résultat en double ;
    - la garde #66 (`_reconcile_blocked`) accompagne une ligne à découper : si le
      découpage est refusé, la ligne n'est pas réconciliée, seulement mise à jour.
- **`team_name`** : la concaténation publiée, même formule que `set_teammates` et que la
  clé `_team_key` du rescrape ; posé seulement sur une ligne découpée (une ligne non
  découpée reste « comme aujourd'hui », FR-008).
- **Compteurs du rapport** : la ligne découpée neuve compte dans `imported`, la reprise
  d'une ligne existante dans `updated` (via `_upsert`, `team_name` change). Pas d'entrée
  `Reassignment` : son format (`ancien`/`nouveau`/`fusion`) est un contrat gelé qui
  décrit un athlète vers un athlète, pas une équipe vers N équipiers.
- **Alternatives considered** : appeler `admin_actions.set_teammates` ligne à ligne :
  journal d'administration faux (aucun administrateur), requêtes unitaires contraires à
  la résolution par lot de #706, `DomainError` à rattraper. Rejeté.

## R7. Création de la composition en lot

- **Decision** : `participation_repository.create_batch` accepte une clé
  `teammate_ids` optionnelle par participation et crée les liaisons dans le même
  `flush`. La reprise d'une ligne existante réutilise `replace_teammates`.
- **Rationale** : préserve le « un seul aller-retour pour les participations neuves » de
  #706 ; la construction des objets de liaison reste dans la couche repository
  (Principe II).

## R8. Couverture de tests par fournisseur (FR-011)

- **Decision** :
  - Tests unitaires de `split_relay_teammates` sur les **valeurs réelles** du sondage,
    reconstituées comme l'import les voit : timepulse (`CANNIOU/OLIVIER Cedric/Leclerc`,
    `HUREAU /HUREAU/PERDREAU Régis /Marianne/Jean-Sebastien`,
    `PINSON/ROCHEFORT-CUNIN Eric/Emmanuel`, `QUILLET/BRILLANT CAMPBELL/ROUSSEAU …`),
    klikego (`MASSONNEAU PIERRE / BESANCON FABIEN .`, rejet de `LE BRAS LUC / LE PAGE
    GUULLAUME .`, `DAUGUET PIERRE E. / BELMONTE ALEXANDRE .`), oktime (`GUILLON RÉMI /
    CHARPENTIER EMMANUEL`), chronoplace (`MENARDAIS FERDINAND / COMPAIN LENA`, rejet de
    `LE BOZEC HENRI / BABINET SYLVAIN`), et rejets breizhchrono, wiclax, klikego
    (groupes, prénoms seuls), chronoweb (`FRATERIES POZZEBON/SKLADZIEN`, `CREUSOTRI`),
    raceresult (`GUILLAUME & ANTHONY`), sporthive (`LA COUSINADE`).
  - Tests de bout en bout scraper → import sur fixtures fichiers existantes :
    `oktime_lacanau_48555.json` (course « Relais L & Duo ») et
    `chronoplace_epreuve_566.html` ; `chronoweb/event_aquathlon_relais.html` et
    `sporthive_relay.json` pour le non-découpage.
  - Tests `_Persister` (sans réseau, `ScrapedResult` construits) : import neuf,
    rescrape idempotent avec et sans dossard, reprise d'une fiche d'équipe existante et
    purge, composition manuelle intacte, garde FR-010, hors relais intact.
- **Limite** : raceresult n'a aucune fixture de relais ; sa couverture est la valeur réelle
  du sondage de juillet (`GUILLAUME & ANTHONY`), non découpée.
