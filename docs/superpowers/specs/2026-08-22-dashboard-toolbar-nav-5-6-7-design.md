# Barre d'outils nommée, état vide unifié, dernières épreuves — design (NAV-5/6/7)

**Issue** : [#483](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/483) (epic #460, audit #325)
**Date** : 2026-08-22
**Statut** : en design

## Le problème

Trois entrées **fort × S** du § 5 de l'audit UI/UX
(`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`), toutes sur
`frontend/app/(public_restricted)/dashboard/page.tsx` et son voisinage
immédiat :

- **NAV-5** — la barre d'outils (`RankTypeToggle`, `DisciplineToggle`,
  `SeasonSelector`) aligne trois contrôles dont aucun n'a de libellé visible ;
  `RankTypeToggle` n'a même qu'un `aria-label` invisible. Sa portée est
  opaque : il ne pilote que les 3 cartes de `StatCardsRank`, pas le reste de
  la page — contrairement aux deux autres contrôles.
- **NAV-6** — `stats.total === 0` (saison sans donnée, ou base neuve) affiche
  un mur de six zéros, avec deux formulations différentes de la même absence
  et aucune cause ni sortie.
- **NAV-7** — la seule liste de l'écran d'atterrissage (`/` y redirige) est
  triée par volume de dossards, jamais par date. `RecentCourses`, annoncé par
  `frontend/AGENTS.md:71` dans `components/dashboard/`, n'existe pas.

Détails, preuves et citations exactes : audit § 5, `[NAV-5]` à `[NAV-7]`.

## Décisions de cadrage

| Question | Décision |
| --- | --- |
| Où va `RankTypeToggle` | Sort de la barre d'outils du haut, se regroupe avec les 3 `StatCardsRank` dans un bloc dédié (voir NAV-5) |
| Comment nommer les 3 contrôles | Un petit libellé visuel (majuscules, même style que les en-têtes de tableau déjà présents dans ce fichier), pas un `<label>` de formulaire — un helper local `FieldLabel`, non exporté |
| Robustesse des tests existants sur la barre | La restructuration change la profondeur DOM ; `data-testid="dashboard-toolbar"` ajouté sur la ligne `Disciplines`/`Saisons`, pour remplacer les assertions fragiles `parentElement` |
| Déclencheur de l'état vide unifié | `stats.total === 0`, calculé dans `page.tsx` avant le rendu |
| Formulation de la cause | Nouvelle fonction pure `seasonAbsenceLabel(selected)` dans `lib/utils/season.ts` — « la saison 2015 — 2016 » (singulier) / « les 3 saisons sélectionnées » (pluriel) |
| Lien « Voir la saison en cours » | Rendu seulement si la sélection courante n'est pas déjà la saison en cours (sinon le lien pointerait sur l'écran déjà affiché) |
| « Bouton primaire existant » de l'attendu | Le CTA `Ajouter une épreuve →` déjà utilisé deux fois dans ce fichier (`Link` stylé `text-sm font-semibold text-accent-ink hover:underline`) — aucun autre candidat dans le périmètre, pas de nouveau composant bouton |
| `RecentCourses` remplace-t-il ou complète-t-il « Épreuves préférées » | **Remplace** — l'audit ne demande pas de garder les deux questions (fréquence *et* récence) sur le même écran, et ajouter une 3ᵉ carte casse la grille 2 colonnes pour un effort qui dépasse le calibrage **S** |
| Tri des épreuves sans date (`event_date: null`) | Exclues du tri chronologique, reléguées en fin de liste (jamais devant une épreuve datée) |
| Colonne remplacée dans le nouveau tableau | La colonne `#` (rang par volume, sans le tri par volume) devient une colonne **Date** — c'est elle que l'utilisateur scanne dans une liste triée par récence |
| Où vit la logique de tri | `sortEventsByDateDesc` dans `lib/utils/event.ts` (pure, testable), pas inline dans le composant — cohérent avec `aggregateDisciplines` déjà extrait dans ce même fichier |
| Export de `EventOut` | `lib/types.ts` exporte désormais `EventOut` (ajout du mot-clé `export`) — nécessaire pour typer la prop de `RecentCourses` |

## NAV-5 — Nommer et regrouper la barre d'outils

**Restructuration de la barre du haut.** Elle ne porte plus que
`DisciplineToggle` et `SeasonSelector`, chacun précédé d'un `FieldLabel`
(« Disciplines », « Saisons ») :

```tsx
<div data-testid="dashboard-toolbar" style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
  <div>
    <FieldLabel>Disciplines</FieldLabel>
    <DisciplineToggle />
  </div>
  <div>
    <FieldLabel>Saisons</FieldLabel>
    <SeasonSelector seasons={seasons} />
  </div>
</div>
```

`FieldLabel` est un helper local (non exporté, défini dans `page.tsx`) qui
reprend le style déjà utilisé pour les en-têtes de la table « Épreuves
préférées » (12px, 700, majuscules, `letter-spacing: .04em`,
`var(--tcn-text-faint)`) — aucun nouveau token, juste sa réutilisation à un
troisième endroit.

**`RankTypeToggle` migre** dans le bloc des 3 cartes qu'il gouverne. La grille
`hero + StatCardsRank` (`page.tsx:76-79`) devient deux zones : la carte héroïque
d'un côté, et de l'autre un conteneur qui porte le libellé + le sélecteur de
rang au-dessus des 3 `StatCard` :

```tsx
<div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] lg:items-start">
  <StatCard variant="hero" .../>
  <div>
    <div className="mb-2 flex items-center justify-between">
      <FieldLabel>Type de rang</FieldLabel>
      <RankTypeToggle />
    </div>
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <StatCardsRank rankCounters={stats.rank_counters} />
    </div>
  </div>
</div>
```

En dessous de `lg`, tout reste empilé en une colonne (comportement identique
à aujourd'hui, juste réordonné : héros, puis libellé + toggle, puis les 3
cartes) ; à `sm` les 3 cartes de rang passent déjà en ligne
(`sm:grid-cols-3`), avant même le palier `lg` où la carte héros se met à
côté du bloc.

Aucun changement de `RankTypeToggle.tsx` lui-même n'est nécessaire : son
`aria-label="Type de rang"` interne reste, et coïncide exactement avec le
texte du `FieldLabel` visuel ajouté à côté (SC 2.5.3 *Label in Name*
respecté sans médaille ARIA supplémentaire).

**Conséquence sur les tests existants.** `dashboard/page.test.tsx` teste
aujourd'hui la position relative de `SeasonSelector` et `DisciplineToggle` via
`screen.getByLabelText("Choisir les saisons").parentElement` — cette
assertion suppose qu'ils partagent un parent direct, ce qui reste vrai après
la restructuration décrite ici *seulement* si on ajoute un niveau de
lookup (`.parentElement.parentElement`) ou, plus robuste, si on cible
directement `data-testid="dashboard-toolbar"`. Le plan choisit la seconde
option — un test qui décrit l'intention (« ces deux contrôles vivent dans la
barre, les tags de saison non ») survit à un changement de profondeur DOM.

**Ne bloque pas NAV-9** : la bande « Ma saison » (#502, hors périmètre)
s'insère comme un frère *avant* le `<div className="mb-4 grid ...">`
ci-dessus — cette restructuration n'en change que l'intérieur, jamais sa
place dans le flux de la page.

## NAV-6 — Un état vide qui nomme la cause

```tsx
const isEmptySeason = stats.total === 0;
```

Quand `isEmptySeason`, tout le contenu sous l'en-tête (titre + barre d'outils
+ tags de saison, qui restent visibles pour permettre d'agir) est remplacé
par un unique `EmptyState` (non `bare` — c'est un état de page, pas une
sous-section) :

```tsx
<EmptyState
  title={`Aucun résultat enregistré pour ${seasonAbsenceLabel(selected)}`}
  description="Change de saison ou ajoute les premiers résultats du club."
  action={
    <div className="flex flex-wrap items-center justify-center gap-4">
      {!isCurrentSeasonSelected && (
        <Link href={voirSaisonEnCoursHref} className="text-sm font-semibold text-accent-ink hover:underline">
          Voir la saison en cours
        </Link>
      )}
      <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
        Ajouter une épreuve →
      </Link>
    </div>
  }
/>
```

Trois pièces, alignées sur le modèle « cause + issue + action » cité par
l'audit (Really Good UX) :

- **`seasonAbsenceLabel(selected)`** (nouvelle fonction dans
  `lib/utils/season.ts`) — mutualise la grammaire singulier/pluriel déjà
  résolue par `seasonSelectionLabel`, mais produit une formulation
  injectable dans une phrase (article + minuscule) plutôt qu'un titre :
  `"la saison 2015 — 2016"` ou `"les 3 saisons sélectionnées"`.
- **`isCurrentSeasonSelected`** — `selected.length === 1 && selected[0] === currentSeason()`.
  Si l'utilisateur regarde déjà la saison en cours (cas de l'installation
  neuve, cf. audit), un lien qui pointe vers l'écran déjà affiché n'apporte
  rien : on ne le rend pas.
- **`voirSaisonEnCoursHref`** — reconstruit `/dashboard` en retirant
  uniquement `seasons` des paramètres actuels de `sp` (les autres, comme
  `sports`, sont conservés — le lien ne change que la saison).

**Hypothèse posée, à vérifier en implémentation** : `stats.total === 0`
implique que `eventsPage.items` et les `by_type` du club sont eux aussi
vides, puisque les trois proviennent du même scope club filtré par les mêmes
`seasons`/`federal_only`. C'est le cas mesuré sur `/dashboard?seasons=2015` ;
aucun scénario connu ne le contredit.

Les deux anciens messages d'absence par carte (« Aucune épreuve
enregistrée », côté disciplines ; le nouveau « Aucune épreuve récente à
afficher » de `RecentCourses`, côté NAV-7) restent en place comme filets de
sécurité défensifs pour un mésalignement plus étroit (par ex. `by_type` vide
alors que `stats.total > 0`) — un cas qui ne devrait pas se produire mais
que le code actuel gardait déjà. Ils ne sont simplement plus **jamais
atteints en même temps** dans le cas `total === 0`, qui court-circuite avant
eux.

## NAV-7 — `RecentCourses` : occuper enfin la place décrite

Nouveau fichier `frontend/components/dashboard/RecentCourses.tsx`, composant
serveur pur (pas de `"use client"` — aucun hook, juste des props et du
JSX), à l'image de ce que `frontend/AGENTS.md:71` annonce déjà :

```tsx
export function RecentCourses({ events }: { events: EventOut[] }) {
  return (
    <Card>
      <h2 style={{ /* identique à "Épreuves préférées" aujourd'hui */ }}>Dernières épreuves</h2>
      {events.length === 0 ? (
        <EmptyState
          bare
          className="py-6"
          title="Aucune épreuve récente à afficher"
          action={<Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">Ajouter une épreuve →</Link>}
        />
      ) : (
        <>
          {/* en-tête de colonnes : Date / Épreuve / Format / Dossards */}
          {events.map((e, i) => (
            <Link key={e.id} href={`/courses/${e.id}`} prefetch={false} className="tcn-rowlink" ...>
              <span>{formatDate(e.event_date) || "—"}</span>
              <span>{formatEventName(e.event_name, e.is_relay)}</span>
              <FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>
              <b>{e.total}</b>
            </Link>
          ))}
        </>
      )}
    </Card>
  );
}
```

Repris tel quel de l'actuelle carte « Épreuves préférées » : le style de
ligne (`tcn-rowlink`), `prefetch={false}` (#425 — jusqu'à 6 liens au-dessus
de la ligne de flottaison), le style de Card/h2, `FormatChip`/`formatToken`.
Seule la colonne `#` (rang par volume) disparaît au profit d'une colonne
**Date** — la donnée que l'utilisateur vient chercher sur cet écran d'après
l'audit — et `formatDate(e.event_date) || "—"` couvre le cas (rare) d'une
épreuve sans date qui se retrouverait quand même dans les 6 premières.

**Tri**, extrait dans `lib/utils/event.ts` (pur, testable indépendamment du
rendu) :

```ts
export function sortEventsByDateDesc(events: EventOut[]): EventOut[] {
  return [...events].sort((a, b) => {
    if (!a.event_date && !b.event_date) return 0;
    if (!a.event_date) return 1;
    if (!b.event_date) return -1;
    return b.event_date.localeCompare(a.event_date); // ISO "YYYY-MM-DD" : tri lexicographique = tri chronologique
  });
}
```

`page.tsx` remplace :

```ts
const topEvents = [...eventsPage.items].sort((a, b) => b.total - a.total).slice(0, 6);
```

par :

```ts
const recentEvents = sortEventsByDateDesc(eventsPage.items).slice(0, 6);
```

et la carte « Épreuves préférées » actuelle par `<RecentCourses events={recentEvents} />`.
Coût réseau nul, confirmé : `eventsPage` est déjà chargé par le
`Promise.all` existant (`page.tsx:38-41`, `page_size: 200`) — ce lot ne
touche à aucun appel API.

`EventOut` (aujourd'hui non exporté dans `lib/types.ts`) devient exporté,
seul changement dans ce fichier — c'est une interface, pas une valeur, sans
effet à l'exécution.

## Ce qui ne change pas

- Palette, couple Anton/Barlow, dégradés `--tcn-*` (identité arbitrée).
- La frontière `components/tcn/` / `components/ui/` : `RecentCourses` est
  100 % public et ne consomme que `Card`/`FormatChip` (`tcn/`) et
  `EmptyState` (`ui/`, déjà utilisé ainsi partout ailleurs dans ce fichier)
  — composition normale, pas un nouveau cas à arbitrer.
- Le comportement de `RankTypeToggle` au clic (pushState, zéro re-fetch,
  #328) et celui de `DisciplineToggle`/`SeasonSelector` (`router.push`,
  #328 aussi, asymétrie voulue) — seul leur habillage visuel/placement change.
- La structure de `GET /stats` et `GET /courses` (aucun champ backend
  touché ; `EventOut`/`Stats` gardent leur forme, seul `EventOut` gagne le
  mot-clé `export` côté TypeScript).
- La grille de stat cards reste insérable d'une bande `NAV-9` au-dessus,
  sans modification requise le jour où #502 démarre.

## Hors périmètre

- **NAV-9** (bande « Ma saison », #502) — non anticipé, non construit.
- **NAV-8** (recherche d'athlète) — lot séparé du même § 5, hors de ce
  périmètre.
- **La mise en avant des podiums récents**, suggérée en complément par
  l'audit NAV-7 (« en complément, la mise en avant des podiums récents ») —
  hors du texte de l'« Attendu » de l'issue #483, qui ne demande que le tri
  par date ; non traité ici.
- **Le cas où `federal_only` masquerait des résultats existants** (saison
  avec des résultats trail/course à pied mais aucun résultat fédéral) —
  l'issue et l'audit ne documentent que la cause « saison sans donnée », pas
  cette cause additionnelle ; la barre d'outils reste visible et actionnable
  au-dessus de l'état vide, ce qui laisse un utilisateur avisé expérimenter,
  mais le message ne la nomme pas explicitement.

## Tests (TDD — Principe III)

Le détail des cas et de l'ordre d'écriture revient au plan
(`writing-plans`), mais le périmètre à couvrir :

- `lib/utils/season.test.ts` — `seasonAbsenceLabel` : singulier, pluriel,
  liste vide (repli sur la saison en cours).
- `lib/utils/event.test.ts` — `sortEventsByDateDesc` : ordre décroissant,
  dates égales, `null` relégué en fin, mélange des deux.
- `components/dashboard/RecentCourses.test.tsx` (nouveau) — rendu des
  lignes, colonne Date via `formatDate`, `prefetch={false}`, état vide
  (« Aucune épreuve récente à afficher » + CTA `/ajouter`).
- `app/(public_restricted)/dashboard/page.test.tsx` — mises à jour
  attendues :
  - les deux tests qui référencent « Épreuves préférées » / « Aucune
    épreuve à afficher » migrent vers « Dernières épreuves » / « Aucune
    épreuve récente à afficher ».
  - nouveau test : `stats.total === 0` rend l'état vide unique et **pas**
    la grille (hero/rank/disciplines/dernières épreuves absents du DOM).
  - nouveau test : le message nomme la saison demandée (`seasons=2015`).
  - nouveau test : le lien « Voir la saison en cours » est absent quand la
    sélection est déjà la saison en cours, présent sinon.
  - `data-testid="dashboard-toolbar"` remplace les lookups `parentElement`
    fragiles dans les tests déjà existants sur la position des tags.
  - nouveaux tests de libellé visible : « Type de rang », « Disciplines »,
    « Saisons » sont chacun présents comme texte à l'écran (pas seulement en
    `aria-label`).

## Questions restées ouvertes

Aucun arbitrage produit non tranché : les points qui auraient pu l'être
(remplacer vs. compléter « Épreuves préférées », visibilité conditionnelle
du lien « Voir la saison en cours », choix de la colonne remplacée) sont
tranchés ci-dessus avec leur justification, dans la marge de décision que
l'issue #483 délègue à l'implémentation. Le seul point à signaler à
l'utilisateur en relecture : le choix de **remplacer** « Épreuves
préférées » plutôt que d'ajouter une 3ᵉ carte est celui qui change le plus
visiblement l'écran actuel — à confirmer avant `writing-plans` si un
attachement particulier existe à conserver le classement par volume.
