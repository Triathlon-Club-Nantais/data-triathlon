# Phase 0 — Recherche

**Feature** : pagination et recherche du classement d'une épreuve (issue #163)
**Date** : 2026-08-03

Tout ce qui suit a été **vérifié sur le dépôt et sur la base**, pas supposé. Les
mesures priment sur ce document en cas de divergence.

---

## R1. L'ordre d'affichage n'est pas celui de la base

**Constat.** `frontend/lib/utils/raceOrder.ts::orderParticipations` trie en
JavaScript : groupe (finisher → DNF → DSQ → DNS), puis, dans le groupe 0, rang
croissant avec les non classés en fin, et dans les autres groupes, temps
croissant avec les temps absents en fin ; le nom départage.
`participation_repository.list_for_course` trie sur `rank_overall` seul.

Tant que la totalité du classement arrivait d'un coup, l'écart était invisible :
le navigateur retriait tout. Paginé, il devient une faute — la tranche N servie
par la base n'est pas la tranche N que l'écran aurait affichée.

**Décision.** L'ordre descend en SQL et devient la seule définition.
`orderParticipations` disparaît de `RaceFinishers`.

**Expression SQL.** Un seul `ORDER BY` doit couvrir deux règles disjointes selon
le groupe. Les clés sont donc gardées par `CASE`, dans cet ordre :

1. `groupe` — `CASE upper(status) WHEN 'DNF' THEN 1 WHEN 'DSQ' THEN 2 WHEN 'DNS' THEN 3 ELSE 0 END`
2. `CASE WHEN groupe = 0 AND rank_overall IS NULL THEN 1 ELSE 0 END`
3. `CASE WHEN groupe = 0 THEN rank_overall END`
4. `CASE WHEN groupe <> 0 AND temps_absent THEN 1 ELSE 0 END`
5. `CASE WHEN groupe <> 0 AND NOT temps_absent THEN total_time END`
6. `lower(nom)`, `lower(prenom)`

`temps_absent` vaut `total_time IS NULL OR total_time = '' OR total_time = '00:00:00'`.

**Pourquoi des booléens plutôt que `NULLS LAST`.** SQLite place les `NULL` en
tête en tri croissant, PostgreSQL en queue. Un `ORDER BY col` nu diverge donc
entre le développement et la production. Les clés 2 et 4 sont des booléens
0/1 : elles ordonnent identiquement partout. C'est déjà le procédé de
`list_for_course` (`Participation.rank_overall.is_(None)`), on le généralise
plutôt que d'introduire `nullslast()`.

**Pourquoi la comparaison de chaînes suffit pour les temps.**
`scrapers/utils.normalize_time` rend systématiquement `HH:MM:SS` sur deux
chiffres d'heures. L'ordre alphabétique coïncide donc avec l'ordre
chronologique en deçà de 100 heures.

**Limite connue, à documenter dans le code.** Le départage final par nom
utilise la collation de la base, là où le JavaScript utilisait
`String.localeCompare`. Les deux ne placent pas les caractères accentués au
même endroit. L'écart n'est observable qu'entre deux lignes partageant **et**
le groupe **et** le rang (ou le temps) — soit des ex æquo. On l'assume plutôt
que d'ajouter une couche de collation.

**Alternatives écartées.** Trier en Python après chargement complet : c'est
exactement ce que la feature supprime. Ajouter une colonne d'ordre calculée à
l'import : une migration et un champ dénormalisé à maintenir, pour une requête
qui porte sur quelques milliers de lignes au plus.

---

## R2. La recherche insensible aux accents n'existe pas aujourd'hui

**Mesure** (SQLite de développement, moteur du projet) :

```
lower('LEMÉE') LIKE '%lemee%'  →  0
lower('LEMÉE') LIKE '%lemée%'  →  1
lower('LEMÉE') LIKE '%LEMEE%'  →  0
```

Le listener `_register_sqlite_unicode_case` de `core/database.py` rend
`lower()` **Unicode-aware** — `LEMÉE` devient `lemée`, pas `lemee`. C'est de la
casse, pas de l'accentuation. PostgreSQL se comporte de la même façon :
`ILIKE` ignore la casse, jamais les accents. La recherche d'athlètes existante
(`athlete_repository`, ligne 93) a donc déjà cette limite.

**Décision** (arbitrée le 2026-08-03) : on implémente l'insensibilité aux
accents, pour cette recherche.

**Mise en œuvre, symétrique des deux côtés** :

- **SQLite** — une fonction `unaccent` enregistrée à la connexion, sur le
  modèle exact de `_unicode_lower` déjà en place : décomposition
  `unicodedata.normalize("NFD", …)` puis retrait des marques combinantes.
- **PostgreSQL** — l'extension `unaccent`, créée par une migration Alembic.

Les deux exposent le même nom, donc un seul appel `func.unaccent(...)` côté
SQLAlchemy. Le terme cherché est déaccentué en Python avant d'être passé.

**Trois risques, tous à traiter explicitement dans les tâches** :

1. **Droits de création d'extension.** `CREATE EXTENSION` peut être refusé
   selon le rôle. La migration utilise `IF NOT EXISTS` et échoue bruyamment
   si le droit manque — préférable à une recherche qui rend 500 en production.
2. **Schéma d'installation sur Supabase.** Les extensions y sont
   conventionnellement installées dans le schéma `extensions`, pas `public`.
   Si `extensions` n'est pas dans le `search_path` du rôle applicatif,
   `unaccent(...)` ne résout pas. À **vérifier sur la base réelle** avant de
   clore la branche ; ce n'est pas vérifiable depuis la suite de tests.
3. **Deux implémentations, une seule couverte.** Les tests tournent sur
   SQLite : le chemin PostgreSQL n'est vérifié par aucun test unitaire. C'est
   la contrepartie assumée du choix, et la raison de la vérification manuelle
   du point 2.

**Coût en performance : nul ici.** `unaccent()` interdit l'usage d'un index sur
la colonne, mais le filtre s'applique toujours à l'intérieur d'une seule
épreuve — quelques milliers de lignes au plus, déjà restreintes par
`course_id`.

**Alternative écartée.** `translate()` en SQL pur : PostgreSQL l'a, SQLite non.
Une colonne dénormalisée déaccentuée : une migration, un champ à maintenir à
chaque import, pour une recherche.

---

## R3. Exprimer « rends-moi tout » dans un paramètre de taille

**Besoin** : FR-006 — `page_size=all` rend le classement entier en une page.

**Décision** : `page_size: int | Literal["all"] = Query(20)`. FastAPI produit un
`anyOf` correct dans l'OpenAPI. Les bornes (`1 ≤ n ≤ 200`) ne peuvent pas être
portées par `Query(ge=…, le=…)` sur une union : elles sont vérifiées dans un
petit résolveur qui rend `int | None` (`None` = pas de découpage) et lève une
erreur d'usage sinon.

**Alternative écartée** : `page_size: str` avec analyse maison — même quantité
de code, mais l'OpenAPI ne décrirait plus qu'une chaîne.

**Alternative écartée** : `page_size=0` pour dire « tout ». Une valeur sentinelle
numérique se confond avec une erreur de calcul côté appelant ; `all` se lit.

---

## R4. Où vit l'agrégation

**Contrainte** : Principe II — `api → services → repositories → DB`, sens unique.

**Décision** :

- `participation_repository` gagne deux fonctions : la tranche ordonnée et
  filtrée du classement (avec son total), et la lecture des colonnes nécessaires
  à la synthèse.
- `stats_service` gagne la synthèse elle-même. C'est déjà le module des
  agrégations (`list_events`, 123 lignes) ; y ajouter une synthèse d'épreuve est
  une réutilisation, pas un mélange.
- Le router se contente de valider et de déléguer.

**Une seule requête pour la synthèse**, ne chargeant que
`status, club, category, total_time, splits` et le genre de l'athlète — pas
d'objets ORM complets, pas de `joinedload`. Six agrégations en Python sur ces
tuples valent mieux que six `GROUP BY` :

- l'histogramme n'a de toute façon **pas** d'expression SQL portable — les temps
  sont des chaînes `HH:MM:SS`, et découper en tranches de 5 minutes demanderait
  un `substr`/`cast` différent sur chaque moteur ;
- `is_tcn` est une **liste blanche Python** (`core/club.is_tcn`), pas une
  expression SQL simple ; la clause `tcn_clause` existe mais l'appliquer par
  club distinct ferait autant de requêtes.

**Le cas de `splits`, à connaître.** C'est de loin la plus lourde des six
colonnes — un objet JSON par ligne —, et la seule chargée pour une raison
indirecte : en déduire `split_keys`. Aucun des deux moteurs n'offre d'extraction
portable des **clés** d'un objet JSON (`json_each` côté SQLite,
`jsonb_object_keys` côté PostgreSQL, sémantiques et disponibilités
différentes), donc on lit la colonne. C'est le prix assumé de colonnes de
tableau stables d'une page à l'autre (FR-028). À rouvrir seulement si la
synthèse se mesure lente.

**Alternative écartée** : réutiliser `list_for_course` puis agréger. Elle charge
des `Participation` complètes avec l'athlète joint — précisément le coût que la
feature supprime.

---

## R5. L'état d'écran vit déjà dans l'URL, ailleurs dans le projet

Rien à inventer, tout est en place :

- `lib/scope.ts` — `SCOPE_PARAM`, `SCOPE_CLUB`, `scopeFromParam()`. Le filtre
  club de `RaceFinishers` s'y branche au lieu de son `useState`.
- `components/layout/ScopeToggle.tsx` — le patron : `useSearchParams` +
  `URLSearchParams` + `router.push` dans un `useTransition`, avec un
  `data-pending` qui atténue le contrôle pendant la navigation.
- `components/results/ResultsFilters.tsx` — le patron de champ de recherche du
  projet : **pas de debounce**, la saisie est locale et s'applique sur `Entrée`
  ou sur un bouton. On le reprend tel quel. C'est plus simple qu'un debounce et
  cela évite une requête par frappe.
- `app/dashboard/page.tsx` et `app/club/page.tsx` — le patron de page serveur :
  `searchParams: Promise<Record<string, string | undefined>>` puis `await`.
  Confirmé par la documentation embarquée
  (`next/dist/docs/01-app/03-api-reference/03-file-conventions/page.md`).

**Conséquence de rendu** : lire `searchParams` rend la page dynamique. C'était
déjà le cas de fait — `serverFetch` utilise `cache: "no-store"`.

**Décision sur la pagination** : des `<Link>`, pas des boutons. Navigables au
clavier, ouvrables en nouvel onglet, fonctionnels avant hydratation (FR-026).

---

## R6. Ce qu'on ne change pas

- **`ParticipationOut` est réutilisé tel quel** pour les lignes du classement,
  bien qu'il imbrique un `CourseBrief` redondant avec la course déjà rendue à
  côté. Sur 20 lignes la redondance est négligeable, et un schéma dédié
  obligerait à faire diverger le type `Participation` du frontend, utilisé par
  d'autres écrans. À reconsidérer seulement si `page_size=all` devient un
  chemin courant.
- **Le découpage de l'histogramme** (tranches de 300 s, 60 tranches au plus) et
  **les limites d'affichage** (8 catégories, 9 clubs) sont transposés à
  l'identique depuis `app/courses/[id]/page.tsx`. La feature déplace ces
  calculs, elle ne les rejuge pas.
- **`core/club.is_tcn`** reste la définition unique de l'appartenance au club
  (#76). La synthèse l'appelle, elle ne la réimplémente pas.
