# Meilleurs temps du club par format calibré et saison (#1588)

## Besoin

La fiche athlète rend un meilleur temps par (discipline, format) depuis #1361,
calculé côté client. La page `/club` n'a rien d'équivalent. On veut, pour la
saison en cours ou toutes saisons, le meilleur temps TCN par format calibré
(XS, S, M, L, XL) et par genre, avec l'athlète, l'épreuve et la date.

## Décisions

- **Calcul côté serveur.** `/club` ne transporte plus les participations
  (#487, #581) : le front ne peut pas réemployer `bestTimes`. Une requête de
  repository, `participation_repository.club_best_time_rows`, rend les colonnes
  candidates en **un seul aller-retour** ; `club_service.get_club_best_times`
  parse les temps (`scrapers.utils.to_seconds(strict=True)`) et garde le premier
  par clé. Le tri en SQL est impossible : `total_time` est une chaîne.
- **Exclusions**, miroir de `performanceExclusion` (`best-times.ts`) : en
  attente (`validated_clause`), relais (résultat **ou** épreuve, comme
  `club_podiums`), épreuve non fiable (`Course.is_reliable` faux ; `NULL`
  compte, comme côté client), non classé (DNF, DNS, DSQ), temps illisible ou
  nul. Seuls les résultats `counts_for_tcn`.
- **Formats calibrés** : les `event_type` canoniques suffixés `-xs/-s/-m/-l/-xl`
  (`scrapers.classify.CANONICAL_TYPES`), filtrés en SQL par `IN`. Les distances
  libres (`10km`) restent hors périmètre.
- **Genre** : `M` et `F` seulement (`core.gender.GENDERS`), un genre vide ne
  nomme pas de « meilleur temps femmes ».
- **Égalité** : la première épreuve courue garde la ligne, puis le plus petit
  identifiant de participation (ordre déterministe).
- **Opposition** : le nom vient de la fiche `Athlete` jointe, déjà anonymisée
  par l'opposition ; aucun autre champ nominatif n'est lu.
- **Contrat** : `GET /api/v1/club/best-times?season=&federal_only=`, ajout pur
  (Principe IV), derrière la garde du site comme le reste du router club.
  `season` absent : toutes saisons. Réponse : une liste plate de
  `ClubBestTime`, triée discipline, taille (XS → XL), genre (F puis M).
- **UI** : carte « Meilleurs temps du club » sur `/club`, onglets « Saison en
  cours » / « Toutes saisons », les deux listes chargées côté serveur en
  parallèle (quelques dizaines de lignes au plus). Une ligne par (discipline,
  format, genre), lien vers la participation, valeur lue « meilleur temps sur
  M », jamais « record ». Carte absente si le club n'a aucun temps comparable.

## Tests

Repository/service : chaque exclusion, format non calibré, égalité, saison vide,
nombre de requêtes constant. API : forme, `season`, `federal_only`. Front :
rendu des lignes, lien, onglet vide, carte absente.
