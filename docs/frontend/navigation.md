# Navigation : rail, barre mobile, tiroir

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## `nav.config.ts` et le rail (#115, #428)

**Navigation** — `components/layout/nav.config.ts` en est la description
**unique** ; ajouter une destination y tient en une ligne. Deux échelons de
visibilité, à ne pas confondre : `minRole` ne distingue qu'anonyme et
connecté — `ROLE.ADMIN` est déclaré mais **inerte**, `rank` ne le vaut jamais,
donc une entrée à cet échelon est invisible pour tout le monde. La finesse
au-delà passe par `permission`, un code de `core/permissions.py` confronté à
`session.permissions` (#115). Un écran livré mais retiré du grand public porte
`preview: true` (#879, les déclarations de crédit bénévole : `/benevolat`
et `/encadrement/benevolat`) : il exige `pages:preview` **en plus** de son
`permission`, une liste de `permission` se lisant en OU, et sa route rend
`PreviewRefusal` à qui ne le porte pas (même idiome que `/club/athletes`,
jamais de redirection). Masque d'interface seulement : les routes de l'API
gardent leurs propres gardes. `/benevoles` (« Validation des épreuves », #271) n'est **pas** concerné et reste ouvert au seul mot de passe bénévoles
(`AccessGate`). La Carte, elle, reste `soon` : sa route répond à tous. Une section que le filtrage vide disparaît. Rien
de tout cela ne garde une donnée : chaque ressource de l'API porte sa propre
garde, et le rail ne fait qu'éviter d'annoncer un écran qui rendrait 403.
**Un seul composant `Entree` rend une destination dans les deux états du
rail** — seuls son style et ses enfants changent avec `expanded` (#428). Deux
composants (une tuile repliée, une entrée dépliée) faisaient basculer React
entre deux branches JSX : le `Link` était démonté puis remonté pour la même
route, et son `IntersectionObserver` neuf retirait un **second prefetch RSC**.
Le rendu serveur partant toujours du rail replié, la resynchronisation
`localStorage` du montage suffit à déclencher la bascule. Même raison pour le
`prefetch={false}` du logo du rail déplié : il double la route de
« Tableau de bord ». Le test verrouille l'invariant en comptant les
**montages** de `next/link` par route — le prefetch ne se reflétant sur aucun
attribut du DOM. Deux bornes à connaître avant de s'y fier :

- **L'invariant ne porte que sur la section racine.** Repliée, une catégorie
  n'offre qu'une tuile qui déplie, pas ses destinations : leurs `Link`
  n'existent pas, donc l'unification ne peut rien y réutiliser et ils
  remontent à chaque dépliage (mesuré : 2 montages de `/club/athletes` après
  un pliage/dépliage à la main, contre 1 pour `/resultats`). Sans conséquence
  à l'atterrissage, où ils ne montent qu'une fois. Le bouton de catégorie est
  resté hors périmètre de #428.
- **La barre mobile garde ses doublons.** Son logo (`/`) et son
  bouton « Ajouter une course » doublent deux entrées du tiroir, exactement
  comme le logo du rail corrigé ici. Hors périmètre de #428 également : sous
  `md` le rail est en `display:none`, le coût réel est celui de l'ouverture
  du tiroir, repayé à chaque ouverture.

## Trois espaces (#1295)

Chaque section porte un `space` (`public`, `encadrement`, `admin`) ; le rail
et le tiroir ne rendent que l'espace de la page, déduit du premier segment
d'URL par `spaceOf`. La barre basse suit l'espace courant. `SpaceSwitcher`
mène d'un espace à l'autre par des liens à icône, tous visibles (#1336), et
disparaît pour qui n'en a qu'un ; son bouton « Back-office » porte le total des
files « À traiter », seule entrée vers le sommaire depuis l'espace public. Sous
`md`, il vit en tête du tiroir, libellés compris, et jamais dans l'en-tête : une
icône seule y passait pour une action, sans survol au doigt pour la nommer
(revue UI/UX de #1353). La palette ⌘K garde les écrans de tous les espaces ouverts.
L'espace Encadrement (Jeunes, Crédits bénévoles) vit sous `/encadrement`, gardé
par `can_supervise` via `components/layout/space-guard.tsx`, partagé avec
`/admin` ; `/encadrement` mène au premier écran ouvert.

## Rail replié, cookie de largeur, nav mobile (#482)

**Rail replié, cookie de largeur, nav mobile** (#482) — le rail replié
porte désormais un monogramme texte lié à `/` en plus du bouton de
pliage (l'en-tête passe en colonne à cet état, faute de place pour les
deux côte à côte), et ses six `title` sont remplacés par
`components/ui/tooltip.tsx` (`@base-ui/react/tooltip`, délai ramené à
0 ms — l'audit reprochait le délai natif d'~1 s, pas seulement son absence
au clavier/tactile). Une section réduite à une seule destination livrée
rend directement son `Entree` au lieu du bouton dépliant — « Club » tenait ce
rôle jusqu'à #487, qui lui a livré `/club` en seconde destination ; la branche
reste vivante par les pouvoirs (« Administration » s'y réduit pour qui n'en
porte qu'un). La largeur du rail (`tcn-nav-expanded`) est désormais un
**cookie**, lu par `app/layout.tsx` avant la peinture plutôt qu'un
`localStorage` relu au montage — la seule exception documentée au refus de
miroir cookie de #467 (`athlete-retenu.md`), parce que le besoin serveur y est authentique et
qu'aucun `fetch()` vers `/api/v1` n'est concerné. Sous `md`, une barre
basse fixe porte les onglets de l'espace courant, marqués `bottomBar` dans
`nav.config.ts` (#1300, #1298 : `BOTTOM_BAR_MAX` par espace, déclarés et non
calculés sur le profil ; le back-office ouvre sur « Sommaire », qui porte le
total « À traiter » ; seuls les onglets publics doivent être visibles sans
session, les autres espaces étant gardés ; `nav.config.test.ts` borne leur
nombre), puis un onglet « Plus », toujours présent, qui ouvre le
tiroir (#1012 : sept onglets à
375 px repliaient leurs libellés sur deux lignes ; cinq au plus tiennent sur
une ligne, ~75 px chacun). Un `labelCourt` change le **texte visible**, et le
nom accessible **commence par lui** (WCAG 2.5.3, commande vocale) : `label`
seul s'il commence déjà par le court (« Validation des épreuves »), sinon
les deux (« Accueil, tableau de bord »). L'onglet courant porte, en plus de
sa couleur, un trait `--tcn-orange` de 3 px (pendant de `barreActive` du
rail, WCAG 1.4.1), et « Plus » s'allume quand la page courante vit dans le
tiroir. Le tiroir porte « le reste » : ce que la barre laisse de l'espace
courant, sections débordantes comprises, et les deux actions primaires, **sauf** repli (#621) : la barre basse est masquée
pendant que le tiroir est ouvert (le `Sheet` passe par-dessus), donc un
visiteur dont la barre porte tout (anonyme, ou adhérent sans pouvoir) se
retrouvait sans aucune destination à l'écran une fois le tiroir ouvert par
le hamburger. `sectionsRepli` (`AppNav.tsx`) retombe alors sur les sections
de l'espace courant (`sections`) ; c'est le seul cas de doublon avec la barre. Dans l'espace public, le tiroir porte
toujours l'arbre complet, barre comprise (Accueil, Résultats, Club et « Mon espace »),
même quand ce dernier rend le reste non vide (#1620) ; encadrement et back-office
gardent le repli seulement si le reste est vide. Le
pied du tiroir ne ferme plus au clic : `UserMenu` ferme lui-même via
`onNavigate`, au moment où la navigation a réellement lieu (immédiat pour la
connexion, après le succès de la mutation pour la déconnexion) — jamais au
clic de « Se déconnecter » seul, qui couperait l'affichage de son état
d'attente.
