# RaceResult — ne plus mutiler les noms d'équipe (issue #63)

Statut : design approuvé, prêt à planifier.
Panel de référence : `2026-07-19-raceresult-api-sondage.md` (§12.3, §12.4).

## 1. Problème

`_build_result` (`backend/app/scrapers/raceresult.py`) appelle `split_athlete_name`
**sans condition** sur la cellule `nom`. Quand la source y met un nom d'équipe,
l'identité est découpée à tort et persistée mutilée. Deux cas mesurés
(§12.3 du sondage, **19 identités** sur 17 épreuves / 10 831 participations) :

- 403144 (Aquaterra, SwimRun L, duo) → `"GUILLAUME & ANTHONY"` :
  `split` s'arrête à `&` (qui n'est pas `isupper()`) → `nom='GUILLAUME'`,
  `prenom='& ANTHONY'`.
- 380823 (Bike & Run de Pontcharra) → `"Les Inconnus Associés"` : aucun bloc
  majuscule → dernière branche de `split` → `nom='Associés'`,
  `prenom='Les Inconnus'`.

La mutilation ne frappe que les noms d'équipe **non entièrement majuscules**. Un
nom d'équipe tout en capitales (`"COLLER AU PARQUET"`, fixture relais 401699)
survit par chance : `split_athlete_name` lui rend `("COLLER AU PARQUET", "")`.

**Ce que la source sait.** La colonne `nom` d'une liste relais vient de
`NomRelais` / `NomEquipe` / `AfficherNoms` (cf. fixture 401699 : `_map_columns`
donne le rôle `nom` à `NomRelais`, `AfficherNoms` part en `extras`). Ces
expressions sont un signal **structurel fiable**.

**Ce que la source ne résout pas.** `is_relay` est écarté (issue #63, §12.4 du
sondage) : le drapeau n'est **pas lu** sur le chemin de création d'athlète
(`mapping.get_or_create_athlete` ne reçoit ni ne lit `is_relay`), donc même une
détection de relais parfaite ne corrigerait rien ; et l'élargir risque de
scinder des `Course` (`UNIQUE(name, event_date, event_type, is_relay)`). Le
correctif est **orthogonal** à `is_relay`.

## 2. Contraintes

- **Ne pas toucher `split_athlete_name`** (`scrapers/utils.py`) : partagé par
  tous les scrapers, et des noms de personne légitimes portent `/` ou `-`. Une
  garde trop large y casserait des cas valides (issue #63, §12.3).
- **Zéro churn sur `_map_columns`** : sa signature est dépliée par ~25 call
  sites de tests. On ne la modifie pas.
- Rester fidèle au style source-truth du module : décider sur l'**expression de
  colonne** plutôt que sur des heuristiques de valeur, sauf filet de sécurité
  explicitement borné et sûr.

## 3. Solution

La décision *découper ou non* passe dans `_build_result`, gardée par
`_est_nom_equipe(nom_col_expr, valeur)`. Si « équipe », le nom entier va dans
`nom`, `prenom=""` ; sinon, `split_athlete_name` comme aujourd'hui.

### 3.1 Détection — `_est_nom_equipe(nom_col_expr, valeur) -> bool`

Deux gardes, dans cet ordre :

1. **Garde par valeur (par ligne)** : `"&" in valeur` → équipe. `&` est un
   séparateur d'équipe sûr, absent d'un nom de personne. Attrape
   `"GUILLAUME & ANTHONY"` quelle que soit la colonne, y compris une colonne
   conditionnelle mixte.
2. **Garde par colonne (structurelle)** : si l'expression **n'est pas**
   conditionnelle — ni `;` ni opérateur de comparaison (`_RE_COMPARAISON`) — et
   que `_peel(nom_col_expr) ∈ {"nomrelais", "nomequipe", "affichernoms"}`, la
   colonne est **entièrement** d'équipe → équipe. Attrape
   `"Les Inconnus Associés"` (colonne `NomRelais`, sans `&`).

**Pourquoi exclure le conditionnel de la garde 2.** `_peel` réduit
`if([Relais]=1;ucase([NomRelais]);[AfficherNom])` à `"nomrelais"` (il retient le
terme le plus long qui ne compare pas). Une garde 2 fondée sur `_peel` seul
traiterait donc cette colonne **mixte** comme « tout équipe » et cesserait de
découper ses lignes **individuelles** (`AfficherNom`) → régression. En excluant
les expressions conditionnelles, la garde 2 ne fire que sur des colonnes
**inconditionnellement** d'équipe ; les lignes d'équipe d'une colonne mixte sont
récupérées par la garde 1 (`&`).

**Pourquoi `affichernoms` (pluriel) et pas `affichernom` (singulier).**
`AfficherNom` nomme **un** individu (à découper) ; `AfficherNoms` concatène les
équipiers (fixture 401699 : `"VIDAL Florian, L'HER Antonin, DUSSUCHAL Pierrick"`).
La distinction tient au `s` final : `_peel("AfficherNom") == "affichernom"`
(hors ensemble), `_peel("AfficherNoms") == "affichernoms"` (dans l'ensemble).

**Pourquoi `&` seul au niveau valeur.** `/` et `-` figurent dans des noms de
personne légitimes (issue #63) : les employer casserait des cas valides. `&`
n'apparaît pas dans un nom de personne. La virgule non plus n'est pas retenue :
`LFNAME` peut rendre `"NOM, Prénom"` (un individu), donc la virgule n'est pas un
séparateur d'équipe sûr — et les listes d'équipiers virgulées de `AfficherNoms`
sont déjà couvertes par la garde 2 (structurelle).

### 3.2 Threading — `_nom_expression(payload, roles) -> str`

Helper placé près de `_map_columns`, qui re-dérive l'expression source de la
colonne ayant gagné le rôle `nom` :

```python
col = roles.get("nom")
if col is None: return ""
data_fields = [str(e) for e in payload.get("DataFields") or []]
return data_fields[col] if col < len(data_fields) else ""
```

`scrape_event_all` la calcule après `_map_columns` et la passe à `_build_result`
via un kwarg **défaulté** `nom_col_expr: str = ""`. Le défaut préserve le
comportement actuel (pas de garde 2, découpage inchangé), donc les call sites
existants de `_build_result` restent verts sans modification.

### 3.3 Forme cible

Pour une identité d'équipe : `athlete_name = <nom d'équipe entier>`,
`athlete_firstname = ""`. Un seul `Athlete` par nom d'équipe, dédoublonné par
`UNIQUE(nom, prenom, birth_date)`. Non mutilant, changement minimal, cohérent
avec `"COLLER AU PARQUET"` qui rend déjà ce résultat aujourd'hui. Modéliser une
entité « équipe » distincte d'`Athlete` est hors périmètre de cette issue.

## 4. Angle mort assumé

Un nom d'équipe **sans `&`** servi par une colonne **conditionnelle**
(`if([Relais]=1;ucase([NomRelais]);[AfficherNom])` rendant p. ex. `"Les Bleus"`)
échappe aux deux gardes : la garde 1 ne voit pas de `&`, la garde 2 exclut le
conditionnel. Non observé au panel. Le fermer exigerait le champ `[Relais]` par
ligne, non exposé de façon fiable. Consigné, non traité — même arbitrage
« bruyant et réversible » que le §12.2 du sondage : une valeur brute visible
plutôt qu'une garde qui casserait des individus d'une colonne mixte.

## 5. Tests

- **Unitaires `_est_nom_equipe`** :
  - `("NomRelais", "Les Inconnus Associés")` → `True` (garde 2).
  - `("ucase([NomRelais])", "les bleus")` → `True` (garde 2, enrobage pelé).
  - `("AfficherNoms", "GUILLAUME & ANTHONY")` → `True` (garde 2 et/ou 1).
  - `("AfficherNom", "Florian VIDAL")` → `False` (individuel, à découper).
  - `("AfficherNom", "GUILLAUME & ANTHONY")` → `True` (garde 1).
  - `("if([Relais]=1;ucase([NomRelais]);[AfficherNom])", "Florian VIDAL")` →
    `False` (conditionnel sans `&` : individu découpé).
  - `("if([Relais]=1;ucase([NomRelais]);[AfficherNom])", "GUILLAUME & ANTHONY")`
    → `True` (garde 1).
  - `("LFNAME", "DUPONT Jean")` → `False`.
- **Unitaire `_nom_expression`** : sur la fixture 401699, rend `"NomRelais"`.
- **Bout-en-bout `_build_result`** (avec `nom_col_expr` threadé) :
  - Fixture relais type 401699 mais `NomRelais = "Les Inconnus Associés"` →
    `nom == "Les Inconnus Associés"`, `prenom == ""`.
  - Colonne `AfficherNoms` valant `"GUILLAUME & ANTHONY"` →
    `nom == "GUILLAUME & ANTHONY"`, `prenom == ""`.
  - Non-régression individuel : `AfficherNom = "Florian VIDAL"` →
    `nom == "VIDAL"`, `prenom == "Florian"` (toujours découpé).
- **Non-régression** : la fixture 401699 existante
  (`test_build_result_categorie_i18n_de_401699_entre_lisible`,
  `"COLLER AU PARQUET"`) reste verte.

## 6. Documentation

Mettre à jour §12.3 / §12.4 du sondage
(`2026-07-19-raceresult-api-sondage.md`) : marquer le défaut « corrigé (#63) »
et renvoyer à ce design pour la garde et l'angle mort.

## 7. Fichiers touchés

- `backend/app/scrapers/raceresult.py` — `_est_nom_equipe`, `_nom_expression`,
  branche de garde dans `_build_result` (+ kwarg `nom_col_expr`), appel dans
  `scrape_event_all`.
- `backend/tests/test_raceresult.py` — tests ci-dessus.
- `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` — §12.3 / §12.4.
