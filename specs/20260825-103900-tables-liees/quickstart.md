# Quickstart — vérifier la feature de bout en bout

**Feature** : `specs/20260825-103900-tables-liees/` (issue #481)

Trois niveaux, du moins cher au plus cher. Les deux premiers sont
reproductibles ; le troisième est manuel et couvre précisément ce que jsdom ne
peut pas prouver.

## Prérequis

Un worktree est une copie neuve : `frontend/node_modules/` n'y est pas (#337).

```bash
cd frontend
npm ci
```

## 1. La suite automatisée

```bash
cd frontend
npm test              # vitest run, deux projets (node + jsdom)
npm run lint          # ESLint
npm run build         # build prod : TypeScript strict + RSC
```

Attendu : **vert**, et le compte de tests supérieur à celui d'avant la branche —
la feature ajoute des tests, elle n'en remplace aucun (`contracts/` C7 : les
tests existants restent, réécrits en rôles là où ils interrogeaient des `div`).

Cibler une seule liste pendant le développement :

```bash
npx vitest run --project jsdom components/results/RaceFinishers.test.tsx
```

## 2. Les adresses dans le rendu serveur (FR-003, contrat C4)

C'est le seul point qui ne se vérifie pas dans jsdom : il porte sur ce que le
serveur écrit.

```bash
# Terminal 1 — backend, port libre publié dans .dev-backend.json
cd backend && uv run python scripts/dev_server.py

# Terminal 2 — frontend, il lit le port du backend de ce worktree
cd frontend && npm run dev
```

Puis, sur une épreuve qui a des participations — le numéro se lit dans
`/resultats` :

```bash
curl -s http://localhost:3000/courses/<ID> | grep -c 'href="/courses/<ID>/participations/'
```

- **Avant la branche** : `0`.
- **Attendu** : le nombre de lignes affichées, soit **20** sur une page par
  défaut (le classement est paginé à 20 depuis #163).

Le site pouvant être derrière le mot de passe partagé (#509), `curl` peut
tomber sur la porte d'entrée : passer le cookie de session obtenu dans le
navigateur, ou vérifier sur un déploiement sans mot de passe configuré.

## 3. Les quatre vérifications manuelles

Ce que les tests ne prouvent pas, et qu'il faut voir.

### 3.1 Le lecteur d'écran nomme les colonnes (FR-001, SC-001)

Sur **chacune des six listes** (`/courses/<id>`, `/resultats`,
`/athletes/<id>`, `/ajouter`, `/dashboard`, et « Top clubs » sur
`/courses/<id>`), avec un lecteur d'écran (VoiceOver, NVDA ou Orca) :

- naviguer en mode tableau, ligne à ligne ;
- **attendu** : chaque valeur est énoncée avec le nom de sa colonne
  (« Temps total, 01:10:47 »), et la structure est annoncée comme un tableau
  avec son nombre de colonnes et de lignes.

C'est **la** vérification qui compte : jsdom ne calcule pas le nom accessible
d'une cellule à partir de son en-tête (`research.md` D7). Un tableau qui passe
tous les tests et qu'un lecteur d'écran n'annonce pas comme un tableau est un
échec de la feature.

### 3.2 Les quatre gestes natifs sur une ligne de classement (FR-004, SC-003)

Sur `/courses/<id>`, une ligne du classement :

| Geste | Attendu |
| --- | --- |
| survol | l'adresse du détail s'affiche dans la barre d'état |
| clic milieu (ou ⌘/Ctrl+clic) | le détail s'ouvre dans un nouvel onglet, le classement reste en place |
| clic droit → copier l'adresse | l'adresse du détail est dans le presse-papiers |
| `Tab` puis `Entrée` | le détail s'ouvre ; **un seul** `Tab` par ligne (FR-011) |

### 3.3 L'attente sur la ligne activée (FR-005, SC-004)

Toujours sur `/courses/<id>` :

- cliquer une ligne : la **ligne cliquée** se voile jusqu'au rendu du détail ;
  aucune autre ligne ne bouge ;
- ⌘/Ctrl+clic sur une ligne : **aucune** attente ne s'allume (la page courante
  ne change pas) ;
- activer « réduire les animations » dans le système, recliquer : l'attente
  reste perceptible, **sans mouvement**.

Si l'attente ne s'allume jamais, vérifier `prefetch={false}` sur la ligne : la
phase d'attente est sautée pour une route déjà préchargée (`research.md` D3).

### 3.4 Aucune régression visuelle (FR-007, SC-005)

Écran par écran, avant/après, sur les six listes : colonnes, largeurs,
gouttières, traits de séparation, retour au survol, anneau de focus, liseré
orange des lignes du club, fond grisé des non-finishers. Et les comportements
de FR-008 : déplier une compétition à plusieurs épreuves dans `/resultats`,
la sous-ligne de preuve et les gestes d'administration sur `/athletes/<id>`,
les états vides et leurs sorties.

Le défilement horizontal **doit rester exactement ce qu'il est** : les largeurs
plancher sont le lot #461, et ce lot part de cette base.

## 4. Fin de branche

Cycle commun aux trois voies (`docs/WORKFLOW-IA.md`) : `requesting-code-review`
→ le sous-agent **`ui-ux-review`** (la branche touche `frontend/`) →
`verification-before-completion` → `finishing-a-development-branch`.

`ui-ux-review` est ici plus qu'une formalité : sa grille couvre l'accessibilité
WCAG AA, et c'est le second regard sur ce que le § 3.1 vérifie à la main.
