# Accès au site et routes hors garde

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Mot de passe d'accès au site (#509)

**Mot de passe d'accès au site (#509)** : `app/(public_restricted)/`
(groupe de routes, invisible dans l'URL — nommé en revue de #513 : ces pages
restent **publiques côté RBAC**, seule leur porte d'entrée est restreinte, et
un nom de dossier jamais rendu dans une URL relève de la couche technique)
accueille tout ce qui exige le mot de
passe partagé — `dashboard`, `resultats`, `athletes/[id]`, `courses/[id]`,
`club`, `carte`, `ajouter`, `guide`, `benevolat` (la liste qui fait foi est
celle de `app/routes-garde-site.test.ts`) — gardé par `app/(public_restricted)/layout.tsx`, un
appel serveur à `GET /api/v1/site-access/session`. Sur refus, ce layout rend
`SiteAccessGate` **à la place** des enfants ; il ne redirige pas vers
`/acces`. Un layout serveur ne reçoit en Next 16 ni le chemin demandé ni les
`searchParams`, donc la redirection perdait la destination — un lien partagé
vers `/courses/42` finissait sur le tableau de bord après la saisie du mot de
passe (relevé en revue de #513). Sur place, l'URL ne bouge pas : le
`router.refresh()` qui suit la connexion rejoue le layout, cookie en main, et
rend la page demandée. Il n'y a donc aucun paramètre `next` à transporter, ni
à valider contre la redirection ouverte. Les deux autres portes étaient
fermées : `middleware.ts` est exclu par design (il ne constate que la
présence du cookie, jamais sa validité) et `authInterrupts`/`unauthorized()`
est encore expérimental en Next 16.3.1. `acces` (formulaire de mot
de passe), `benevoles`, **`admin` et `login`** restent des routes **sœurs**,
hors du groupe, jamais soumises à cette garde — `acces` reste le formulaire
atteint en direct ou après déconnexion, d'où la prop `apres="accueil"` qui
pousse vers `/` là où le rendu sur place se contente de rafraîchir ;
`benevoles` garde sa propre garde client (`AccessGate`, #271) — et sa
recherche d'athlètes passe par `GET /benevoles/athletes`, un jumeau gardé par
le mot de passe bénévoles, puisqu'un bénévole n'a jamais celui du site (revue
de #513). **`admin` et
`login` sont hors du groupe** parce qu'ils forment, à eux deux, le seul chemin
navigateur qui pose le tout premier mot de passe sur un déploiement neuf
(`site_access_config` vide, garde fail-closed) : `admin` seul ne suffisait pas
— sa propre garde renvoie un anonyme vers `/login`, et `login` rangé sous
le groupe refermait la boucle en `/admin` → `/login` → `/acces` → impasse,
aucun mot de passe n'existant encore à saisir (relevé en revue de #513, après
la sortie d'`admin` en revue finale de #509). Le placement des deux côtés est
désormais tenu par `app/routes-garde-site.test.ts`, un test de structure de
dossiers : c'est une erreur de rangement, invisible à la lecture d'un fichier.
Les deux gardent la garde qui les protégeait déjà, indépendante de #509
(`app/admin/layout.tsx`, SSO/RBAC ; `login` n'expose que des boutons de
fournisseur). La révocation
d'urgence (#169) vit **dans** `admin/acces` : par adresse ligne à ligne,
globale en carte de bas de page. Pas d'écran ni d'entrée de navigation
dédiés — un unique bouton ne les justifiait pas. Jumelle de la CLI, la
redondance étant le but : le back-office suppose une session, la CLI non.

**`mon-compte`** (#1663) est aussi une route sœur : supprimer son compte ne
doit pas dépendre du code d'accès au site. Sa garde est celle d'`encadrement`
(`spaceRefusal`, `app/mon-compte/layout.tsx`) avec un pouvoir toujours accordé :
elle ne fait que renvoyer un anonyme vers `/login`.

## Textes légaux (#333)

**Textes légaux** (#333) : `/mentions-legales`, `/confidentialite`, `/cgu`
sont des routes **sœurs** du groupe gardé : un non-adhérent, qui n'a pas le
code, doit pouvoir lire ce que le club fait de ses résultats
(`routes-garde-site.test.ts` le tient). Leur contenu vit en TSX dans
`components/legal/content/`, rendu par `LegalPage` ; les liens du pied de
page viennent de `legal-routes.ts` et sont rendus par `VersionFooter`, donc
sur toutes les routes. Deux règles : `updatedAt` change **dans le même
commit** que le texte, et les faits juridiques (base légale, durées,
sous-traitants) viennent de la décision
`docs/superpowers/specs/2026-10-01-base-legale-decision.md` (#332), qui
prime. Un nouveau cookie, un nouveau prestataire ou une nouvelle donnée
collectée rend la politique fausse tant qu'elle n'est pas mise à jour.
