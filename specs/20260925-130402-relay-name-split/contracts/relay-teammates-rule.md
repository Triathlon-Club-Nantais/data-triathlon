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
4. **Segments** (sinon) : couper la valeur sur `/`. Pour chaque segment :
   - contient `&`, `+` ou le mot `et` (toute casse) → `None` ;
   - casse mixte : les jetons majuscules forment **un seul** bloc contigu, en tête ou en
     queue → (bloc, reste) ; sinon `None` ;
   - tout en majuscules : **exactement deux** jetons → (1er, 2e) ; sinon `None` ;
   - aucune majuscule → `None`.
5. Chaque nom et chaque prénom porte au moins deux lettres.
6. Nombre d'équipiers entre 2 et 8.
7. Aucune paire en double (comparaison sans accents ni casse).

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
| `LE BRAS LUC / LE PAGE GUULLAUME .` (klikego, 3 jetons) | `None` |
| `LE BOZEC HENRI / BABINET SYLVAIN` (chronoplace) | `None` |
| `DAUGUET PIERRE E. / BELMONTE ALEXANDRE .` | `None` |
| `DAMIEN/FRANCOIS Francois et Benjamin` (breizhchrono) | `None` |
| `ECN / USCAL Sarah et Francois` | `None` |
| `FRATERIES POZZEBON/SKLADZIEN` (chronoweb) | `None` |
| `MARTIN Jean DUPONT / Paul` (« Prénom NOM » réordonné) | `None` |
| `LES BARBAPAPAS Alex et Margot`, `TIC & TAC .`, `OGGY ET LES CAFARDES`, `CREUSOTRI`, `LA COUSINADE`, `GUILLAUME & ANTHONY`, `S. D.` | `None` (pas de `/`) |
| `A/B/C Jean/Paul` (longueurs différentes) | `None` |
| `DUPONT Jean / DUPONT Jean` | `None` |
