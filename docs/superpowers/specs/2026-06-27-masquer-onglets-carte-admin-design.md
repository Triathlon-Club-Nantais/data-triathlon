# Simplifier les onglets — masquer Carte & Admin — design

**Date** : 2026-06-27
**Statut** : à valider
**Issue** : [#10 — simplifier les onglets](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/10)
**Branche cible** : `claude/issue-10-specification-kyyszj` (nouvelle, depuis `main`) → PR Draft

## Objectif

Alléger la barre de navigation principale du frontend en **masquant** les
onglets **Carte** et **Admin**. L'onglet **Club** est **conservé**. Les pages
et le code des onglets masqués sont **préservés** (masquage, pas suppression)
afin de pouvoir les réafficher plus tard sans reconstruire la fonctionnalité.

## Contexte (issue #10 + commentaires)

- Demande initiale (@Vinzzou) : « on peut enlever, pour le moment, les onglets
  club, carte et admin ».
- Question (@tjarrier) : « à supprimer totalement […] ou juste à "cacher" dans
  le but de les réafficher plus tard ? »
- **Décision finale** (@Vinzzou) : « on garde **club** pour le moment, et on
  **masque carte et admin** ». Précisions :
  - **Admin** : « il y aura une page un jour à faire, donc à cacher en
    attendant » → masquer, code conservé.
  - **Carte** : « si un jour on veut faire un truc pourquoi pas » → masquer,
    code conservé.
  - **Club** : finalement conservé (était hésitant car « ça ne marchait pas la
    dernière fois », mais demande à le garder le temps d'y réfléchir).

→ Le périmètre se réduit donc, par rapport à la demande initiale, à **masquer
Carte et Admin uniquement**, sans rien supprimer.

## Décisions actées

| Décision | Choix |
|----------|-------|
| Onglets retirés de la nav | **Carte** et **Admin** |
| Onglet Club | **Conservé** (inchangé) |
| Mode de retrait | **Masquage** (cacher de la barre), **pas suppression** — réversible en une ligne |
| Pages/routes `/carte` et `/admin` | **Conservées** (fichiers `app/carte/page.tsx`, `app/admin/page.tsx` + composants intacts) ; restent atteignables par URL directe |
| Code API `/admin/*` (client/serveur/queries) | **Inchangé** (back-end et data-layer non touchés) |
| Tests | Pas de test ciblant la nav aujourd'hui ; en ajouter un léger pour figer le contrat |

## Périmètre — modifications

### 1. Barre de navigation (seul changement applicatif)

Fichier : `frontend/components/layout/TcnTopbar.tsx`.

Le tableau `NAV` (lignes 9-15) pilote intégralement les onglets affichés et
constitue le **seul** endroit où `/carte` et `/admin` sont liés dans la nav
(vérifié : aucun autre `Link`/lien de navigation vers ces routes ; les
occurrences `/admin/...` dans `lib/api/client.ts` et `lib/api/server.ts` sont
des **chemins d'API back-end**, à ne pas toucher).

État actuel :

```ts
const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club" },
  { href: "/carte", label: "Carte" },   // ← à masquer
  { href: "/admin", label: "Admin" },   // ← à masquer
];
```

**Approche retenue — drapeau `hidden` explicite** (plutôt qu'une simple
suppression de lignes) : on garde les entrées dans `NAV` mais marquées
masquées, et on les filtre au rendu. Intention documentée dans le code,
réaffichage = retirer un drapeau.

```ts
// `hidden: true` → onglet temporairement masqué (issue #10). Code et page
// conservés ; réafficher en retirant le drapeau.
const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club" },
  { href: "/carte", label: "Carte", hidden: true },
  { href: "/admin", label: "Admin", hidden: true },
];
```

Au rendu, filtrer avant le `.map` :

```tsx
{NAV.filter((item) => !item.hidden).map((item) => { /* … inchangé … */ })}
```

*Alternative envisagée* : supprimer purement les deux lignes du tableau. Plus
court, mais perd la trace de l'intention « masqué, à réafficher » dans le code.
Le drapeau `hidden` est préféré pour l'auto-documentation et la réversibilité.

### 2. Test de non-régression (léger)

Ajouter un test (Vitest + RTL) sur `TcnTopbar` qui vérifie que la barre rend
les onglets **Tableau de bord / Résultats / Club** et **n'affiche pas** les
libellés **Carte** et **Admin**. But : figer le contrat de visibilité pour
éviter une réintroduction accidentelle.

*Pré-requis à vérifier à l'implémentation* : présence d'un setup RTL/jsdom dans
`frontend/` (le composant est `"use client"` et utilise `usePathname`/
`useRouter` de `next/navigation`, à mocker). Si l'outillage de test du composant
n'est pas trivial à mettre en place, ce point est **optionnel** et peut être
traité séparément — le changement de la section 1 reste autosuffisant.

## Hors périmètre

- **Aucune suppression** de page, route, composant (`app/carte/`, `app/admin/`,
  `components/map/`, `components/admin/`) ni de code data-layer/API.
- **Onglet Club** : aucune modification (conservé tel quel).
- Refonte du contenu des pages Club / Carte / Admin (« je vais réfléchir » côté
  Club) → sujets distincts, hors de cette issue.
- Back-end : aucun changement (les endpoints `/admin/*` restent en place).

## Vérification (critères de succès)

- `cd frontend && npm run dev` → la barre n'affiche plus **Carte** ni **Admin** ;
  **Tableau de bord, Résultats, Club** présents et fonctionnels.
- Accès direct à `/carte` et `/admin` par URL → pages toujours rendues (preuve
  que c'est un masquage, pas une suppression).
- `cd frontend && npm run lint` → propre.
- `cd frontend && npm run build` → build prod OK (TS strict).
- `cd frontend && npm test` → tests verts (incluant le test de nav si ajouté).
- `grep -n "Carte\|Admin" frontend/components/layout/TcnTopbar.tsx` → les entrées
  existent toujours mais portent `hidden: true`.

## Réversibilité

Réafficher un onglet plus tard = retirer son `hidden: true` dans `NAV`
(et, le cas échéant, ajuster/supprimer l'assertion correspondante du test de
nav). Aucune reconstruction de page nécessaire.

## Notes

- Le périmètre réel (masquer **2** onglets, Carte + Admin) est plus étroit que
  la formulation initiale de l'issue (qui citait aussi Club) ; il reflète la
  **dernière** décision du fil de commentaires.
- Changement volontairement minimal et localisé (un fichier de nav, + un test
  optionnel) pour rester trivialement réversible.
