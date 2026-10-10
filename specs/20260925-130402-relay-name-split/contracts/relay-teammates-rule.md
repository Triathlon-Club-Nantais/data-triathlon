# Contrat : `split_relay_teammates` (#895)

Fonction pure, `backend/app/scrapers/utils.py`. Aucun contrat HTTP ni CLI ne change :
`ParticipationOut.teammates`, `ParticipationOut.team_name` et
`ClubPodiumEntry.teammate_names` existent depuis #894 et gardent leur forme.

```python
def split_relay_teammates(published: str) -> list[tuple[str, str]] | None:
    """(nom, prénom) de chaque équipier, dans l'ordre publié, ou None."""
```

**Entrée** : la valeur publiée d'une ligne **de relais**, telle que l'import la
reconstitue : `" ".join(filter(None, [athlete_name, athlete_firstname]))`. L'appelant ne
l'appelle jamais hors relais.

**Sortie** : 2 à 8 paires `(nom, prénom)`, espaces normalisés, casse publiée conservée ;
ou `None` (ligne non découpée). Jamais de liste partielle.

## Règle

1. Retirer les jetons faits uniquement de `.` ; normaliser les espaces.
2. Pas de `/` → `None`.
3. **Listes parallèles** : `(noms, prénoms) = split_athlete_name(valeur)`. Si les deux
   contiennent `/` : couper chacun sur `/`, retirer les espaces ; même nombre
   d'éléments exigé ; paires position à position.
4. **Duo « noms d'abord »** (klikego 517 et 518, #1270, #1282), sinon : la valeur
   publiée, avant l'étape 1, lit `NOM1 / NOM2 Prénom1 / Prénom2 .`, exactement deux `/`
   et le `.` final présent (il écarte les noms d'équipe des autres fournisseurs,
   `BREIZH / IRON MEN / TCN`). Chaque nom est **un seul** mot tout en majuscules. Les
   prénoms prennent l'une de deux formes :
   - un mot tout en majuscules chacun (`GUERIN / LE_ROUX JULIEN / MARC .`) ;
   - un à trois mots en casse mixte chacun, aucun tout en majuscules : le passage
     majuscules → casse mixte marque la frontière nom/prénom
     (`GUERIN / ROUX Jean Paul / Anne Sophie .`). C'est la forme réellement publiée
     (#1282).

   → `[(NOM1, Prénom1), (NOM2, Prénom2)]`. Un `.` isolé ailleurs qu'en fin de valeur
   rejette le libellé, sans nettoyage. Un `_` y tient lieu d'espace : chaque mot est
   coupé sur `_` et recollé par une espace, morceaux vides ôtés (`LE__ROUX_` → `LE ROUX`).
   Un nom composé publié avec une espace (`LE ROUX`) ne suit pas cette étape.
5. **Segments** (sinon) : couper la valeur sur `/`. Pour chaque segment :
   - contient `&`, `+` ou le mot `et` (toute casse) → `None` ;
   - casse mixte : les jetons majuscules forment **un seul** bloc contigu, en tête ou en
     queue → (bloc, reste) ; sinon `None` ;
   - tout en majuscules : deux jetons → (1er, 2e) ; au-delà, une particule (`LE`, `DE`,
     `DU`, `DOS`…, liste `_NAME_PARTICLES`) se colle au jeton qui la suit, et il doit
     rester deux mots dont un seul porte la particule : il est le nom, en tête ou en
     queue (#1237) ; sinon `None`. `VAN` n'est pas une particule (intercalaire
     vietnamien : `NGUYEN VAN ANH` reste indécidable). Limite connue : un nom
     vietnamien `LE` (`LE ANH TUAN`) se lit `("LE ANH", "TUAN")`, faux découpage
     qu'on ne peut exclure sans perdre `LE TULZO NICOLAS` ;
   - aucune majuscule → `None`.
6. Chaque nom et chaque prénom porte au moins deux lettres.
7. Nombre d'équipiers entre 2 et 8.
8. Aucune paire en double (comparaison sans accents ni casse).

Tout échec d'une étape → `None`.

## Exemples (valeurs réelles du sondage)

| Valeur reconstituée | Sortie |
| --- | --- |
| `CANNIOU/OLIVIER Cedric/Leclerc` (timepulse) | `[("CANNIOU", "Cedric"), ("OLIVIER", "Leclerc")]` |
| `HUREAU /HUREAU/PERDREAU Régis /Marianne/Jean-Sebastien` | 3 paires, `("PERDREAU", "Jean-Sebastien")` en dernier |
| `PINSON/ROCHEFORT-CUNIN Eric/Emmanuel` | `[("PINSON", "Eric"), ("ROCHEFORT-CUNIN", "Emmanuel")]` |
| `LEGEARD/LEGEARD/LEGEARD Anne/Paul/Marc` (famille) | 3 paires distinctes |
| `MASSONNEAU PIERRE / BESANCON FABIEN .` (klikego) | `[("MASSONNEAU", "PIERRE"), ("BESANCON", "FABIEN")]` |
| `GUILLON RÉMI / CHARPENTIER EMMANUEL` (oktime) | `[("GUILLON", "RÉMI"), ("CHARPENTIER", "EMMANUEL")]` |
| `MENARDAIS FERDINAND / COMPAIN LENA` (chronoplace) | `[("MENARDAIS", "FERDINAND"), ("COMPAIN", "LENA")]` |
| `DUPONT Jean / MARTIN Paul` | `[("DUPONT", "Jean"), ("MARTIN", "Paul")]` |
| `LE TULZO NICOLAS / LE TULZO ROXANE .` (klikego, épreuve 400, #1237) | `[("LE TULZO", "NICOLAS"), ("LE TULZO", "ROXANE")]` |
| `LE BRAS LUC / LE PAGE GUULLAUME .` (klikego) | `[("LE BRAS", "LUC"), ("LE PAGE", "GUULLAUME")]` |
| `LE BOZEC HENRI / BABINET SYLVAIN` (chronoplace) | `[("LE BOZEC", "HENRI"), ("BABINET", "SYLVAIN")]` |
| `GUERIN / LE_ROUX JULIEN / MARC .` (klikego 517, #1270) | `[("GUERIN", "JULIEN"), ("LE ROUX", "MARC")]` |
| `BOUTIER_LAURET / PETIT ANNE_SOPHIE / LUC .` (klikego 518, #1270) | `[("BOUTIER LAURET", "ANNE SOPHIE"), ("PETIT", "LUC")]` |
| `GUERIN / LE_ROUX Julien / Marc .` (klikego 517, forme publiée, #1282) | `[("GUERIN", "Julien"), ("LE ROUX", "Marc")]` |
| `BOUTIER_LAURET / DE_LA_TOUR Anne / Luc .` (#1282) | `[("BOUTIER LAURET", "Anne"), ("DE LA TOUR", "Luc")]` |
| `GUERIN / ROUX Jean Paul / Marc .` (prénom composé à gauche, #1282) | `[("GUERIN", "Jean Paul"), ("ROUX", "Marc")]` |
| `GUERIN / ROUX Julien / Anne Sophie .` (prénom composé à droite, #1282) | `[("GUERIN", "Julien"), ("ROUX", "Anne Sophie")]` |
| `GUERIN / LE ROUX JULIEN / MARC .` (nom composé non soudé) | `None` |
| `GUERIN / ROUX Julien / MARC .` (casse des prénoms mêlée) | `None` |
| `GUERIN / ROUX Jean Paul Louis Marie / Marc .` (prénom de quatre mots) | `None` |
| `GUERIN / ROUX Julien . / Marc .` (`.` isolé en trop) | `None` |
| `BREIZH / IRON MEN / TCN` (nom d'équipe, sans `.` final) | `None` |
| `MARTIN JEAN PIERRE / DUPONT PAUL` (3 jetons sans particule) | `None` |
| `DA SILVA DOS SANTOS / DUPONT PAUL` (deux mots à particule) | `None` |
| `NGUYEN VAN ANH / DUPONT PAUL` | `None` |
| `DAUGUET PIERRE E. / BELMONTE ALEXANDRE .` | `None` |
| `DAMIEN/FRANCOIS Francois et Benjamin` (breizhchrono) | `None` |
| `ECN / USCAL Sarah et Francois` | `None` |
| `FRATERIES POZZEBON/SKLADZIEN` (chronoweb) | `None` |
| `MARTIN Jean DUPONT / Paul` (« Prénom NOM » réordonné) | `None` |
| `LES BARBAPAPAS Alex et Margot`, `TIC & TAC .`, `OGGY ET LES CAFARDES`, `CREUSOTRI`, `LA COUSINADE`, `GUILLAUME & ANTHONY`, `S. D.` | `None` (pas de `/`) |
| `A/B/C Jean/Paul` (longueurs différentes) | `None` |
| `DUPONT Jean / DUPONT Jean` | `None` |
