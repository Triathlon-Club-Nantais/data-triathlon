# Rail replié lisible, hydratation sans saut, nav mobile hors du hamburger (#482) — design

Lot #482 de l'epic #460 (arriéré d'audit UI/UX, #325) : `NAV-2` + `NAV-3` +
`NAV-4` du rapport (`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`,
§5). Un seul fichier de fond, `frontend/components/layout/AppNav.tsx` (650
lignes), un seul test de rendu (`AppNav.test.tsx`) — le regroupement en un lot
existe pour éviter trois branches concurrentes sur le même fichier.

Contraintes non négociables, héritées de #325 et non rejugées ici :
**identité arbitrée** (palette, couple Anton/Barlow, dégradés `--tcn-*`
intouchés) et **frontière `components/tcn/` vs `components/ui/`**
(`frontend/AGENTS.md`). L'invariant de montage unique d'`Entree` (#428) — un
seul composant pour les deux états du rail, pour ne jamais démonter/remonter
un `Link` déjà dans le viewport — est préservé et **réutilisé**, pas rouvert.

## Vue d'ensemble des trois entrées

| | Problème mesuré | Correctif |
|---|---|---|
| NAV-2 | Rail replié sans marque, `title` illisible au tactile/clavier, « Club » n'est qu'un bouton pour une seule destination | Monogramme texte lié à `/dashboard`, infobulle accessible sur les pastilles, tuile-lien pour les sections à une seule destination |
| NAV-3 | Rail replié → déplié après la peinture (212 px de saut) | Largeur décidée côté serveur via cookie, lu par `app/layout.tsx` |
| NAV-4 | Toute la nav mobile derrière un hamburger, jamais de repère de page | Barre basse fixe pour les 3 destinations publiques, hamburger réduit à l'administration + le compte, fermeture du tiroir restreinte à la navigation réelle |

Fichiers touchés : `frontend/components/layout/AppNav.tsx` (le gros du
travail), `frontend/app/layout.tsx` (lecture du cookie, réservation d'espace
sous le contenu mobile), `frontend/app/globals.css` (deux tokens de
dimension), `frontend/components/auth/UserMenu.tsx` (un callback de
navigation), et un nouveau `frontend/components/ui/tooltip.tsx`. `nav.config.ts`
n'est **pas modifié** : tout ce qui suit est de la logique de rendu, la table
reste la description unique de l'arborescence.

## NAV-2 — rendre le rail replié lisible

### Le monogramme

Aucun asset « mark » carré n'existe dans `public/` : `logo-tcn.png` est un
wordmark 2000×638, illisible réduit à 76 px de large. Plutôt qu'ajouter un
asset, le monogramme est le texte `CLUB_NAME_SHORT` (« TCN »,
`lib/club.ts`) posé dans la police déjà arbitrée pour les affichages de
marque (`--tcn-font-display`, Anton) — aucune identité nouvelle, juste une
troisième occurrence du même procédé déjà utilisé pour les initiales de
`Avatar`. **Décision tranchée ici, pas une question produit** : introduire un
second asset graphique (un mark carré dérivé du logo) aurait été
disproportionné pour ce lot et aurait rouvert l'identité visuelle, hors
mandat.

Contrainte de place : l'en-tête du rail fait 76 px de large sur 68 px de
haut, et le bouton de pliage (44×44) l'occupe déjà presque entièrement en
largeur (48 px de contenu utile une fois les 14 px de marge de chaque côté
soustraits). Le monogramme ne peut donc pas cohabiter **à côté** du bouton de
pliage replié — il n'y a pas la place. Il se **superpose en hauteur** : l'en-tête
passe d'une rangée (bouton + logo côte à côte, inchangé à l'état déplié) à
une colonne quand replié — bouton de pliage en haut, monogramme-lien en
dessous, tous deux centrés. Le bouton garde sa taille de cible tactile
(44 px), le monogramme est un second élément interactif distinct (lien vers
`/dashboard`, pas un doublon du bouton). Reste dans la même hauteur de
bandeau (68 px) : pas de saut de layout pour le reste de la colonne.

### Le remplacement des `title`

Six emplacements du fichier posent aujourd'hui `title={expanded ? undefined :
"…"}` (ou l'équivalent inconditionnel pour les tuiles de catégorie) : le
bouton « Se connecter » replié, « Ajouter une course », « Rechercher un
athlète », « Mon profil » (tuile athlète retenu), la tuile d'une catégorie
repliée (`onExpand`), et `Entree` elle-même. C'est le sous-ensemble exact des
« huit pastilles » de l'audit — le septième `title` du fichier
(« Ne plus choisir », sur la croix de désélection) ne s'affiche **que** rail
déplié, hors du périmètre de NAV-2, et reste en `title` natif : l'étendre
aurait élargi le lot sans preuve d'audit à l'appui.

Choix entre les deux options de l'audit (micro-libellé sous l'icône vs
infobulle maison survol+focus) : **infobulle maison**, via un nouveau
`components/ui/tooltip.tsx` enveloppant `@base-ui/react/tooltip` — dépendance
déjà présente dans `node_modules` (même famille que `ui/sheet.tsx`, déjà bâti
sur `@base-ui/react/dialog`), simplement jamais encore enveloppée. Deux
raisons l'emportent sur le micro-libellé texte :

- Une tuile de 44 px n'a pas la hauteur pour un libellé lisible sous l'icône
  sans grossir toute la grille verticale du rail (paddings et hauteurs
  actuelles calées sur 44 px, référencées à plusieurs endroits du fichier) ;
  une infobulle flotte dans un portail, donc ne contraint aucune dimension
  existante.
- Base UI ouvre nativement au survol **et** au focus clavier, et ferme sur
  `Échap`/perte de focus — exactement le comportement demandé, sans
  réimplémenter une temporisation ou une gestion de focus maison (principe
  du dépôt : s'appuyer d'abord sur les dépendances déjà présentes).

`aria-label` reste en place partout où il l'est déjà : l'infobulle est un
correctif pour l'utilisateur **voyant** (souris ou clavier) qui n'a
aujourd'hui aucun texte visible avant ~1 s d'attente ou pas du tout au
tactile ; les technologies d'assistance avaient déjà leur nom accessible.

### La section à une destination

`nav.config.ts` déclare aujourd'hui « Club » avec une seule entrée livrée
(`athletes-saison`, les autres `soon`). Le rendu du rail replié
(`AppNav.tsx:541-545`) teste aujourd'hui seulement `!expanded && !sec.root` :
la condition devient `!expanded && !sec.root && sec.items.length === 1`, avec
un second embranchement pour rendre directement l'`Entree` unique plutôt que
le bouton `onExpand`. Générique par construction : si une deuxième section un
jour n'a plus qu'une destination livrée, elle bascule automatiquement, sans
retoucher ce fichier — et si « Club » regagne une deuxième destination
(#242), elle repasse tout aussi automatiquement en bouton dépliant.

Test existant à réviser (signalé ici pour `writing-plans`, pas traité dans ce
design) : `AppNav.test.tsx`, describe « arborescence », test « cache les
entrées à venir d'une section qui en porte aussi une livrée (#274) » —
asserte aujourd'hui `getByRole("button", { name: "Club" })` sur le rail
replié ; l'assertion doit devenir un lien vers `/club/athletes`.

## NAV-3 — le double saut à l'hydratation

### Cohérence avec le précédent « pas de cookie miroir » (#467)

`frontend/AGENTS.md` documente un arbitrage récent, distinct de ce lot : le
stock `tcn-athlete` (athlète retenu) reste en `localStorage` seul, sans copie
en cookie relue côté serveur — trois raisons y sont données, dont « aucun
rendu serveur n'en a besoin » et le coût de cache sur les routes qui
dépendent de la fenêtre de revalidation de 30 s (#352), un rendu qui
dépendrait d'un cookie par visiteur n'étant plus partageable au niveau du
**Data Cache** (les appels `fetch()` vers `/api/v1`). Ce même paragraphe
prévoit lui-même l'exception : « Seul un besoin serveur authentique — une
requête API qui dépendrait de l'athlète retenu — rouvrirait l'arbitrage ; de
la mise en avant, non. »

La largeur du rail est précisément ce cas d'exception, pas une contradiction
du précédent : le besoin serveur est authentique (peindre la bonne largeur
dès le premier octet est tout l'objet de NAV-3, impossible sans qu'un
composant serveur connaisse la préférence), et surtout **aucun appel
`fetch()` vers l'API n'est concerné** — le cookie ne sert qu'à calculer un
`initialExpanded` passé en prop à un composant client, jamais relayé vers le
backend. Il ne touche donc pas au Data Cache ni à sa fenêtre de 30 s. De
plus, `app/layout.tsx` est déjà rendu dynamiquement pour **chaque** requête,
cookie ou non (`await connection()`, #448, pour le nonce CSP) : lire un
cookie de plus dans une coquille déjà 100 % dynamique n'entame aucun
partage de cache qui n'était pas déjà absent. Le précédent #467 et ce
cookie ne se contredisent pas : le premier écarte un miroir sans
destinataire serveur, le second en introduit un qui a exactement ce
destinataire.

### Ce qui est traité : la largeur du rail

`app/layout.tsx` est déjà une fonction serveur asynchrone (`await
connection()` y tourne déjà pour le nonce CSP, #448). Elle lit le cookie
`tcn-nav-expanded` via `cookies()` de `next/headers` (patron déjà en place
dans `lib/api/server.ts` : `const jar = await cookies()`) et passe
`initialExpanded={jar.get("tcn-nav-expanded")?.value === "1"}` à `<AppNav
initialExpanded={...} />`. Le nom du cookie reprend celui de l'actuelle clé
`localStorage` (`STORE_NAV`) : seul le support de stockage change, pas le
nom, pour qu'un lecteur du diff retrouve le même repère.

Côté client, `AppNav` initialise son état `expanded` directement depuis la
prop plutôt que depuis un `useEffect` post-montage : le rendu serveur ET
la première passe client partagent la même valeur dès la première peinture,
plus de bascule 76→288 px après coup. `setExpanded` écrit désormais
`document.cookie` (`path=/`, `max-age` d'un an, `SameSite=Lax`) au lieu de
`window.localStorage.setItem`.

**Pas de migration de l'ancien `localStorage`** : un visiteur qui avait
déplié son rail avant ce correctif le retrouve replié une fois, jusqu'au
prochain clic sur le bouton de pliage, qui écrit le nouveau cookie. Cohérent
avec le principe du dépôt de ne pas empiler de couche de compatibilité pour
une préférence d'affichage à faible enjeu — écrire un pont de migration
`localStorage → cookie` aurait été la complexité que ce principe exclut
explicitement pour un gain marginal.

`athlete` et `kbd` restent hydratés en `useEffect` (ils dépendent de
`localStorage`/`navigator`, indisponibles côté serveur) — seul `expanded`
sort de ce mécanisme différé, ce qui simplifie l'effet de montage existant
(`AppNav.tsx:50-65`) à deux valeurs au lieu de trois.

### Ce qui est délibérément laissé de côté : le saut de session

L'audit décrit un **second** saut, indépendant : `useSession` (client, sans
`initialData`) peint d'abord la nav en anonyme, puis lui ajoute jusqu'à deux
sections une fois la session résolue. La section « Attendu » de l'issue #482
ne mentionne, pour NAV-3, que « la largeur du rail décidée avant la peinture
(cookie…) » — pas la session. Le résoudre pleinement demanderait de
préchauffer React Query côté serveur (une frontière d'hydratation dans
`app/layout.tsx`, en s'appuyant sur `serverFetchAuthed` de
`lib/api/server.ts`, qui existe déjà mais n'est utilisé nulle part pour
`/auth/me`) — un chantier d'une toute autre taille que l'effort **M** annoncé,
et qui déborderait largement le fichier unique visé par ce lot.

**Décision** : ce second saut reste hors périmètre de #482, documenté
explicitement plutôt que traité en silence ou étendu sans mandat. C'est le
point de ce design le plus proche d'un arbitrage produit — signalé comme tel
dans le rapport final, pour confirmation ou réouverture explicite par
l'utilisateur.

## NAV-4 — sortir la navigation mobile du hamburger

### La barre basse

Nouvel élément `md:hidden`, `position: fixed; bottom: 0`, dans le fragment
rendu par `AppNav`. Ses destinations ne sont **jamais** codées en dur : elles
se dérivent de `sections.filter(s => s.minRole === ROLE.ANON).flatMap(s =>
s.items)` — aujourd'hui « Tableau de bord », « Résultats », « Athlètes par
saison », exactement les trois destinations publiques citées par l'audit.
Le jour où « Carte » sort de `soon` (#10, #28), elle apparaît ici sans
retoucher ce fichier — même philosophie que la table `nav.config.ts` déjà en
place pour le rail. Chaque destination réutilise l'icône déjà déclarée dans
`nav.config.ts` (cohérence rail/tiroir/barre basse, aucune nouvelle icône à
choisir), porte son libellé en clair, et `aria-current="page"` via `isActive`
(déjà présent dans `AppNav`, aucune duplication de logique).

Nom accessible distinct de celui du rail (`aria-label="Navigation
principale"` déjà pris) pour que deux repères de navigation ne portent pas le
même nom à l'écran : `aria-label="Navigation"` pour la barre basse.

Espace réservé : la barre étant en position fixe, elle sort du flux et
recouvrirait le bas du contenu sans compensation. Deux tokens dimensionnels
rejoignent `--tcn-nav-rail`/`--tcn-nav-panel` dans `app/globals.css` (par
exemple `--tcn-nav-bottom: 64px` — valeur exacte à ajuster en implémentation
selon le rendu réel des libellés) ; `app/layout.tsx` applique un
`padding-bottom` de cette hauteur sous `md`, `0` au-delà (le rail prend le
relais et la barre basse est déjà `md:hidden`). C'est le deuxième petit
compagnon de `app/layout.tsx` dans ce lot, en plus de la lecture du cookie —
la contrainte de #482 est d'éviter trois branches concurrentes sur le
**gros** fichier (`AppNav.tsx`), pas d'interdire deux ou trois lignes
ailleurs.

### Le hamburger réduit

Le tiroir mobile (`Sheet`) reçoit aujourd'hui l'intégralité des `sections`
filtrées par rang. Il ne reçoit désormais que celles dont `minRole >
ROLE.ANON` (« Administration », « Gestion des utilisateurs » aujourd'hui) —
les sections publiques ayant migré vers la barre basse. Les deux actions
primaires ancrées en tête du tiroir (« Ajouter une course », « Rechercher un
athlète ») ne bougent pas : elles restent des doublons assumés avec la barre
du haut mobile, hors périmètre de #428 comme déjà noté dans le fichier — ce
lot n'y touche pas.

Pour un visiteur anonyme, le tiroir réduit n'a donc plus de section à
afficher (« Administration » et « Gestion des utilisateurs » exigent
`ROLE.CONNECTED`) : il garde les deux actions primaires en tête et le pied
compte (« Se connecter »). Le hamburger reste utile même sans section — c'est
la seule porte vers la connexion en mobile en dehors de la barre basse, qui
ne porte que du public.

### La fermeture du tiroir restreinte à la navigation

Aujourd'hui, tout le pied du tiroir (`<div onClick={() =>
setDrawerOpen(false)}><UserMenu pleineLargeur /></div>`, `AppNav.tsx:294-299`)
ferme le tiroir au moindre clic — y compris un clic sur « Se déconnecter »,
qui masque le tiroir avant que son état d'attente (`UserMenu.tsx:72`,
`logout.isPending`) n'ait pu s'afficher.

**Décision, avec une nuance sur l'énoncé de l'issue** : retirer purement et
simplement l'`onClick` englobant laisserait le tiroir ouvert après un clic
sur « Se connecter », qui navigue par `router.push` sans démonter `AppNav`
(le composant vit dans le layout racine, monté une fois pour toute la
session de navigation côté client) — un tiroir resterait visible par-dessus
`/login`. La restriction demandée par l'issue (« aux liens de navigation »)
se traduit donc précisément par : fermer au moment où une navigation **a
réellement lieu**, jamais avant.

`UserMenu` gagne un prop optionnel `onNavigate?: () => void`, appelé à deux
endroits distincts de son propre code, chacun au bon moment :
- au clic sur « Se connecter », juste avant `router.push("/login")` —
  c'est une navigation immédiate, rien à attendre ;
- dans le `onSuccess` de la mutation de déconnexion, aux côtés du
  `router.push("/")` déjà présent — après que la mutation a fini, jamais au
  clic lui-même, pour que l'état d'attente du bouton reste visible le temps
  de la requête.

Le commentaire actuel de `UserMenu` (« Ne prend aucun callback : une prop
fonction ferait l'objet d'un avertissement de sérialisation de Next ») ne
s'applique pas ici : cet avertissement ne concerne qu'un Composant Serveur
passant une fonction à un Composant Client à travers la frontière RSC.
`UserMenu` n'est aujourd'hui rendu que par `AppNav`, lui-même `"use client"`
— aucune frontière serveur/client n'est traversée à l'un ou l'autre de ses
deux points d'appel actuels (rail et tiroir). Le commentaire sera corrigé
pour documenter cette nuance plutôt que supprimé sans explication, au cas où
un futur appelant serveur réintroduirait la question.

## Ce que ce lot ne touche pas

- `nav.config.ts` — aucune ligne modifiée, la table reste la source unique.
- Le regroupement par catégorie du rail/tiroir desktop (`eyebrow`, sections
  dépliables à plusieurs entrées) — NAV-2 ne change que le cas à une seule
  destination.
- Le second saut de session de NAV-3 (cf. plus haut) — hors périmètre
  assumé, à confirmer par l'utilisateur.
- `NAV-5` (barre d'outils du tableau de bord) — lot distinct, déjà en
  worktree (`issue-483-dashboard-toolbar`).
- Toute identité visuelle (palette, typographie, dégradés) et la frontière
  `components/tcn/` vs `components/ui/` — non rejugées.

## Testing (aperçu — le détail TDD revient à `writing-plans`)

`AppNav.test.tsx` reste le seul fichier de test à faire évoluer. Trois
familles de changements à anticiper :
- Le test #274 sur la tuile « Club » repliée (assertion bouton → lien,
  détaillé plus haut).
- Les deux tests de persistance du rail par `localStorage`
  (`tcn-nav-expanded`, decrits `describe("AppNav — doublon de prefetch après
  resynchro localStorage (#428)")`) : la seed passera par une prop
  `initialExpanded` sur le harnais `afficher()` plutôt que par une écriture
  `localStorage` avant montage.
- Nouveaux tests : tuile-lien à une destination, infobulle accessible
  (ouverture au focus, pas seulement au survol), contenu et
  `aria-current` de la barre basse, portée réduite du tiroir (sections
  publiques absentes, sections privées présentes selon les pouvoirs),
  non-fermeture du tiroir avant la fin de la mutation de déconnexion.

## Question ouverte pour l'utilisateur

Le second saut de NAV-3 (session client sans `initialData`) est laissé hors
périmètre par lecture stricte de la section « Attendu » de #482, qui ne cite
que le cookie de largeur. Si l'intention était de le couvrir aussi dans ce
lot, il faut le rouvrir explicitement — ce serait alors un effort
sensiblement supérieur au M annoncé (préchauffage React Query côté serveur),
probablement un lot à part.
