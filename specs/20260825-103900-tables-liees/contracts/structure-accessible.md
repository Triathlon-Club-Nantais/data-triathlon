# Contrat — la structure accessible des six tableaux publics

**Feature** : `specs/20260825-103900-tables-liees/` (issue #481)

Ce contrat n'est pas une API : c'est ce que les six listes exposent à l'aide
technique, et c'est la forme sous laquelle les tests l'interrogent. Il est écrit
en **rôles**, jamais en balises — FR-009 l'exige, et c'est ce qui permet de
changer la mise en œuvre sans réécrire les tests.

## C1 — Chaque liste s'annonce comme un tableau

| Ce que le test demande | Attendu |
| --- | --- |
| `getByRole("table")` | exactement un par liste rendue |
| `getAllByRole("row")` | 1 (en-tête) + une par entrée affichée |
| `getAllByRole("columnheader")` | autant que de colonnes de la liste |
| `getAllByRole("rowgroup")` | ≥ 2 (l'en-tête, et au moins un corps) |

**Zéro ligne** : le tableau est rendu **exactement là où l'en-tête l'est
aujourd'hui** — FR-007 interdit de faire apparaître ou disparaître une en-tête.
Le comportement actuel est hétérogène, et on le suit liste par liste plutôt que
de l'harmoniser, ce qui serait hors périmètre :

| Liste | Vide → |
| --- | --- |
| `RaceFinishers`, `ajouter`, « Top clubs » | `table` **rendu** (`<tbody>` vide), `EmptyState` rendu **après** le tableau, dans le même conteneur |
| `RecentCourses`, `EventsTable`, `EventList` | **aucun** `table` — ces trois-là masquent déjà leur en-tête |

Assertions : `getAllByRole("row")` vaut **1** (la seule en-tête) sur les trois
premières ; `queryByRole("table")` rend `null` sur les trois dernières.

*Corrigé à l'implémentation* : `EventList` était d'abord rangée avec les
premières. Le code dit l'inverse — `EventList.tsx:121` sort **avant** la `Card`
sur `!isLoading && events.length === 0` et rend un `EmptyState` à sa place. La
répartition ci-dessus est celle du code, relue fichier par fichier.

L'`EmptyState` n'est **jamais** un `row`. La variante « une ligne à cellule
unique en `colSpan` » a été écartée : `colSpan` est ignoré par une ligne en
`display: grid` (il faudrait `gridColumn: "1 / -1"`), soit un piège de plus sur
six listes pour un gain nul.

## C2 — Chaque colonne a un en-tête nommé, et les cellules s'y rattachent

Pour chaque liste, les libellés d'en-tête attendus sont ceux d'aujourd'hui —
`data-model.md` § 1 en porte l'inventaire. Le test les interroge par leur nom :

```
getByRole("columnheader", { name: "Temps total" })
```

Les colonnes **sans libellé** (trois au total) restent sans libellé : leur
en-tête existe pour tenir la piste, et le test vérifie qu'elles ne portent pas
un nom inventé.

**Le rattachement cellule↔colonne** se vérifie par la position dans la ligne :
`within(ligne).getAllByRole("cell")[i]` porte la valeur de la colonne `i`.
jsdom ne calcule pas le nom accessible d'une cellule à partir de son en-tête —
c'est la limite assumée de `research.md` D7, et la vérification finale est
manuelle (`quickstart.md` § 3).

## C3 — La ligne activable est annoncée pour ce qu'elle fait

| Liste | Rôle de la cible | Assertion |
| --- | --- | --- |
| Classement d'une épreuve | **lien** | `within(ligne).getByRole("link")` porte un `href` vers le détail du résultat |
| Liste des épreuves — épreuve | **lien** | `href` vers l'épreuve |
| Liste des épreuves — groupe | **bouton** | `getByRole("button", { expanded: false \| true })` |
| Épreuves d'un athlète | **lien** | `href` vers le détail de la participation |
| Derniers résultats enregistrés | **lien** | `href` vers l'épreuve |
| Dernières épreuves | **lien** | `href` vers l'épreuve |
| Top clubs | **aucune** | `within(ligne).queryByRole("link")` rend `null` |

**Deux assertions négatives, et elles sont le cœur de la non-régression** :

- `queryByRole("button", { name: /voir le détail/i })` rend `null` sur le
  classement — c'est le défaut d'origine (FR-002), et un test qui ne
  vérifierait que la présence du lien laisserait passer sa réapparition.
- **Un seul arrêt clavier par `<tr>`** (FR-011) — le compte se fait **par
  ligne, jamais par entrée ni par `<tbody>`** : 1 sur une ligne activable, 0 sur
  une ligne inerte. La distinction n'est pas rhétorique : une entrée
  d'`EventsTable` porte légitimement plusieurs éléments focalisables (lien de
  preuve, gestes d'administration de #439), répartis sur **deux** `<tr>` — le
  compte par entrée y vaudrait 3 et l'assertion échouerait à tort. Un `href`
  par cellule passerait le reste de C3 et casserait celui-ci.

## C4 — La page rendue par le serveur porte les adresses

FR-003 ne se vérifie pas dans jsdom : c'est le rendu serveur qui est en cause.
Le contrat est une commande, portée par `quickstart.md` § 2 — la page d'un
classement récupérée sans exécuter de script doit contenir **une adresse de
détail par ligne affichée**, soit 20 sur une page par défaut, contre 0
aujourd'hui.

**Cette couverture est manuelle et ponctuelle, et il faut le savoir.** Le test de
C3 constate qu'une adresse existe dans le DOM rendu par jsdom ; il ne dit rien de
ce que le serveur écrit. Rien n'échouerait donc si la ligne redevenait un jour
cliente-seule — or c'est exactement la nature du défaut corrigé ici : ce qui
n'est pas dans le HTML n'existe pour personne. La commande de `quickstart.md`
§ 2 est le **seul** garde de FR-003 : la relancer à chaque modification de la
ligne du classement, et reporter son résultat dans la description de la PR. Un
garde automatisé sur le rendu serveur reste une suite possible ; il n'est pas
dans ce lot.

## C5 — Le tri s'annonce, sur le classement seul

| Colonne | `aria-sort` attendu |
| --- | --- |
| colonne triée, ordre croissant | `ascending` |
| colonne triée, ordre décroissant | `descending` |
| autre colonne **triable** | `none` |
| colonne non triable | attribut absent |

Le bouton de tri reste **à l'intérieur** de l'en-tête et garde son `aria-label`
actuel, qui annonce l'action **à venir**. Les deux ne font pas doublon :
`aria-sort` dit l'état, le bouton dit l'effet. Les cinq autres listes n'ont pas
d'en-tête triable et ne portent jamais `aria-sort`.

## C6 — L'attente est perceptible, et seulement quand elle a lieu

- Pendant une navigation cliente déclenchée par une ligne du classement, cette
  ligne porte un état d'attente **visible et sans mouvement**.
- Aucune autre ligne ne le porte.
- Une ouverture en nouvel onglet ne l'allume pas.

Ces trois points se vérifient à la main (`quickstart.md` § 3) ; en test, seule
la **présence du mécanisme** est verrouillée — la ligne du classement porte
`prefetch={false}`, sans quoi l'état d'attente serait sauté en production
(`research.md` D3).

## C7 — Rien d'autre ne bouge

Le contrat visuel est celui d'aujourd'hui (FR-007) : colonnes, largeurs,
gouttières, traits, survol, anneau de focus, liseré orange des lignes du club,
fond grisé des non-finishers. Et le contrat fonctionnel aussi (FR-008) :
dépliage d'une compétition, sous-ligne de preuve et d'administration, marqueurs
d'épreuve non fiable et de résultat en attente, badges de place et de statut,
états vides et leurs sorties, chargement à la volée de la liste des épreuves.

Les tests existants des six listes sont la mesure de ce contrat : **ils doivent
rester verts**, et là où ils interrogent la structure par des `<div>`, ils sont
réécrits en rôles — jamais supprimés.
