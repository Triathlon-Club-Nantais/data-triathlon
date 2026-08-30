# Fusion des variantes de libellé de club, généralisée à tous les clubs

Issue : #635 (suite #200/#215). Discussion source : #223.

## Contexte

#215 a résolu, pour le seul TCN, le fait que « Top clubs » d'une synthèse
d'épreuve affichait le même club sur 2-3 lignes selon la saisie du
chronométreur (`TRI CLUB NANTAIS`, `TRIATHLON CLUB NANTAIS`, `TCN`…). Le
mécanisme retenu (`core/club.is_tcn` + `TCN_CANONICAL_NAME`) reste explicitement
borné au TCN — la fusion pour les autres clubs a été renvoyée à cette issue.

**Mesure de terrain** (lecture seule sur la base de prod, `club-labels`) :
- La casse et l'espacement sont déjà couverts par `normalize_club` (utilisé par
  `is_tcn`) — ce n'est pas la source de variantes observée en dehors du TCN.
- Les vraies variantes rencontrées sont des abrégations lexicales, hors de
  portée d'une normalisation mécanique : `LA ROCHE VENDEE TRIATHLON` (344
  participations) / `LA ROCHE VENDEE TRI` (314), `LES SABLES VENDEE TRIATHLON`
  (401) / `LES SABLES VENDEE TRI` (276).
- Une part significative des libellés n'est **pas** un club : `NANTES (44000)`,
  `NANTES (44100)`, `NANTES (44300)`, `BREST (29200)`, `RENNES (35000)`,
  `La Baule-Escoublac (44500)` (ville + code postal, licence sans club déclaré),
  `INDIVIDUEL`, `Licence Experience`, `-`, `X`. Un algorithme de similarité de
  chaîne (distance d'édition) rapprocherait ces libellés de bruit entre eux ou
  d'un vrai club, sans que ce soit un rapprochement valide.

Conclusion tirée de cette mesure, validée avec l'utilisateur : la détection
automatique par similarité est écartée au profit d'une **curation manuelle
assistée** — aucun faux positif possible, le coût du bruit ci-dessus reste nul
tant qu'un administrateur ne choisit pas explicitement de le regrouper.

## Décisions de conception (arbitrées en session)

1. **Détection : curation manuelle assistée.** Pas de suggestion automatique
   par similarité de chaîne — le risque de faux positif sur le bruit mesuré
   (libellés ville/code postal, licences sans club) est jugé trop élevé pour un
   premier jet. L'administrateur repère les libellés à regrouper par ses propres
   moyens, comme il le fait déjà pour le TCN.
2. **Périmètre : « Top clubs » et le filtre `?club=`**, tous les deux — pas
   seulement l'agrégat d'affichage comme l'avait fait #215. Sans le filtre, une
   ligne canonicalisée de « Top clubs » ne correspondrait à aucun résultat de
   filtre, ou à un sous-ensemble incohérent.
3. **Mécanisme séparé de celui du TCN.** `counter_scope.club_labels`/`is_tcn`
   (panneau `/admin/portee-compteurs`) reste intact et continue de servir
   exclusivement le comptage (`scope=club`). Le nouveau mécanisme est
   indépendant, pour la canonicalisation d'affichage/filtre de tous les autres
   clubs. Compromis assumé : le TCN reste décrit dans **deux** listes
   distinctes (son ensemble de comptage, et — s'il en a besoin côté
   affichage/filtre — sa propre entrée dans le nouveau mécanisme n'est
   **pas** nécessaire : `is_tcn` continue de gouverner son cas dans « Top
   clubs » et dans le filtre, cf. plus bas). Alternative (unifier les deux
   mécanismes) écartée : coût de migration et risque sur l'invariant
   `LastClubLabelError` jugés disproportionnés pour ce ticket.
4. **Découverte : identique au patron existant.** Pas de nouvel écran listant
   les libellés bruts distincts dans l'admin — l'administrateur continue de
   s'appuyer sur `python -m app.cli club-labels` (déjà l'outil de repérage pour
   le TCN, cf. docstring de `is_tcn`), puis saisit à la main dans le panneau.
   Une évolution vers une liste intégrée à l'écran reste possible en suite si
   la curation s'avère trop lente en pratique — hors périmètre ici.

## Modèle de données

Nouvelle table `club_alias`, dénormalisée sur le patron de
`counter_scope_entry` — un « club canonique » n'est pas une entité séparée,
seulement le regroupement des lignes qui partagent le même `canonical_name` :

```
club_alias
  id                    PK
  canonical_name        str   — nom affiché, texte libre (ex. "Racing Club Nantais")
  alias_normalized      str   — UNIQUE, forme normalisée (core.club.normalize_club)
  created_by_user_id    FK users, nullable (cohérence avec counter_scope_entry)
  created_at            timestamp
```

`alias_normalized` étant unique, un même libellé normalisé ne peut pas être
rattaché à deux noms canoniques différents — le service refuse en 409
(`DuplicateError`, même patron que `counter_scope.add_entry`).

**Pas de registre en mémoire.** `counter_scope` en a besoin parce que `is_tcn`
est appelé ligne à ligne par le thread d'import en tâche de fond,
performance-critique. Le nouveau mécanisme n'est consulté qu'à la demande —
synthèse d'épreuve, filtre — jamais pendant le scrape. Une lecture base
classique (une requête par appel, jamais par ligne) suffit : plus simple, sans
la contrainte de réassignation atomique de `counter_scope.load`.

## Consommation

**`stats_service.course_summary`** (point exact de la fusion TCN aujourd'hui,
`stats_service.py:297`) :

```python
libelle = (
    TCN_CANONICAL_NAME if is_tcn(club)
    else alias_map.get(normalize_club(club)) or club.strip()
)
```

`alias_map` (`dict[str, str]`, alias normalisé → nom canonique) est chargé une
seule fois par appel via le repository, jamais par ligne — l'épreuve la plus
chargée porte ~1800 participations (#163), un lookup par ligne serait un N+1.

**Filtre `?club=` de `GET /courses/{id}`** (`participation_repository.py:653`,
aujourd'hui `Participation.club == club`) passe d'une égalité stricte à une
comparaison **normalisée** sur un ensemble de cibles :

```python
cibles = {normalize_club(club)}
if is_tcn(club):  # le paramètre demande explicitement le TCN
    cibles |= counter_scope.tcn_club_labels()
else:
    cibles |= club_alias_repository.aliases_for_canonical(db, club)
query = query.filter(_normalise_sql(Participation.club).in_(cibles))
```

C'est strictement **additif** par rapport à l'égalité stricte d'aujourd'hui
(Principe IV respecté : tout ce qui matchait avant matche encore — un libellé
sans alias enregistré retombe sur `{normalize_club(club)}` seul, comportement
inchangé). Corrige au passage une incohérence déjà présente pour le TCN :
aujourd'hui, filtrer sur `Triathlon Club Nantais` (le nom que « Top clubs »
affiche) ne matche aucune participation dont le libellé brut diffère
verbatim — le filtre et l'agrégat d'affichage divergent silencieusement depuis
#215. Cette correction fait partie du périmètre décidé (point 2 ci-dessus).

`_normalise_sql` est déjà exporté par `core/club.py` (utilisé par
`tcn_clause`) — réutilisé tel quel, pas de second miroir SQL.

## Administration

Nouvel écran, sur le patron de `CounterScopeCard.tsx` : un formulaire nom
canonique + alias en texte libre, une liste des alias existants groupés par nom
canonique, un geste de retrait par alias (`DangerConfirm`, cohérent avec les
gestes destructifs du back-office, #499 — un retrait ne supprime aucune
donnée, juste une association d'affichage, donc geste **neutre**, sans
confirmation renforcée, à la différence du retrait d'un libellé TCN).

Aucune protection « dernier alias » n'est nécessaire (contrairement à
`LastClubLabelError` pour les libellés TCN) : retirer le seul alias d'un
groupe fait simplement retomber ce club sur son libellé brut en affichage —
aucun compteur ne tombe à zéro, contrairement au retrait du dernier libellé
TCN qui viderait `scope=club`.

**API** — nouveau pouvoir dédié `club_aliases:manage` (jamais le préfixe
`/admin/`, convention du dépôt, #115/FR-018) :

- `GET /admin/club-aliases` — toutes les entrées, groupées par `canonical_name`
  côté front (comme `GET /admin/counter-scope` rend les deux listes).
- `POST /admin/club-aliases` — `{canonical_name, alias}` ; crée le groupe s'il
  n'existe pas encore, ajoute un alias sinon.
- `DELETE /admin/club-aliases/{id}` — retire un alias.

Journal d'administration (`admin_action_log`) sur le même patron que
`counter_scope.entry_add`/`entry_remove`.

## Hors périmètre

- La fusion physique des données stockées : `Participation.club` garde son
  verbatim, seul l'affichage et le filtre basculent — même principe que #215.
- Toute suggestion automatique par similarité de chaîne (distance d'édition,
  chevauchement de tokens) — écartée en amont, cf. « Décisions de conception »
  point 1.
- `Athlete.club` et le roster club (`club_roster`, `/club/summary`) — non
  touchés par #215 non plus ; la question ne s'est pas posée pour eux dans
  cette issue.
- Un écran listant les libellés bruts distincts dans l'admin (remplaçant la
  CLI comme outil de repérage) — cf. « Décisions de conception » point 4.
- Unifier ce mécanisme avec `counter_scope.club_labels` — cf. « Décisions de
  conception » point 3.
