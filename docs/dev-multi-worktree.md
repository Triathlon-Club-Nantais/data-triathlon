# Dev multi-worktree

Plusieurs worktrees tournent en parallèle sans configuration. Le backend
(`backend/scripts/dev_server.py`) laisse l'OS lui attribuer un **port éphémère** —
un `--port 8001` figé faisait échouer le second worktree sur « Address already in
use » — et publie ce port dans `.dev-backend.json` à la racine du worktree
(gitignoré, un par worktree).

Deux adresses, deux rôles, à ne pas confondre (`BIND_HOST` / `CLIENT_HOST`) : on
**écoute** sur `0.0.0.0` — comme en prod (`--host 0.0.0.0` du Dockerfile et de
`render.yaml`), sans quoi l'API est injoignable depuis l'extérieur d'un conteneur —
et le scan de ports bind cette même adresse, sinon il déclarerait libre un port
qu'uvicorn ne pourrait pas prendre. Mais l'URL **publiée** (et celles du frontend)
reste en `127.0.0.1` : `0.0.0.0` désigne des interfaces d'écoute, pas une
destination, et seul Linux la tolère en connexion sortante. Le frontend ne bind
rien de son côté — `next dev` écoute déjà `0.0.0.0` par défaut.

`npm run dev` (`frontend/scripts/dev.mjs`) lit ce fichier, **vérifie que le port
répond** (un backend tué par `kill -9` laisse son fichier derrière lui), puis lance
`next dev` avec `BACKEND_URL` **et** `API_URL` renseignés. Les deux comptent : la
première alimente les rewrites `/api/*` de `next.config.ts`, la seconde les fetch RSC
de `lib/api/server.ts`. Sans elles, le front d'un worktree tapait `localhost:8001` en
dur, donc la base d'un autre worktree, **sans erreur visible**.

La découverte ne fait que **combler** : le lanceur n'injecte une variable que si
personne ne l'a définie, et les `.env*` comptent autant que le shell — c'est le
loader de Next lui-même (`@next/env`, épinglé sur la version de `next`) qui les lit
dans `dev.mjs`. Écraser les deux variables aurait rendu `.env.local` muet (Next ne
fait jamais primer un fichier `.env` sur l'environnement reçu) et supprimé la seule
façon de dissocier la cible SSR (`API_URL`) de celle des rewrites (`BACKEND_URL`),
qui diffèrent en prod.

Le code applicatif garde partout sa sémantique `process.env.X || défaut` : la
découverte vit dans les deux lanceurs de dev, jamais sur un chemin de production.
L'ordre de démarrage est libre — lancé en premier, le front attend le back (60 s,
puis repli signalé). Échappatoires : `DEV_BACKEND_PORT` (port imposé côté backend),
`BACKEND_URL` (cible imposée côté frontend, aucune attente), `API_URL` (cible SSR
seule) — au choix dans le shell ou dans `frontend/.env.local`.

Le lanceur rend le sort de `next` : code propagé tel quel, et **128+n** quand l'enfant
est tué (`pkill`, OOM-kill) — un « 1 » forfaitaire ferait passer un arrêt pour une
panne applicative (`scripts/exit-code.mjs`). Ctrl-C ne passe pas par là : SIGINT frappe
tout le groupe de processus, le lanceur meurt du signal et l'appelant voit déjà 130.

Côté backend, le port vient de l'OS (`bind` sur le port 0), pas d'un scan à partir
de 8001. Le scan avait un **point de départ déterministe** : deux worktrees démarrés
au même instant trouvaient le même « premier port libre », d'où une boucle de reprise
à trois essais pour rattraper la collision. Un port éphémère supprime la cause, donc
le rattrapage.

**Un worktree se crée depuis la racine.** `.claude/worktrees/` est résolu depuis le
répertoire **courant** de la session : lancé depuis `frontend/`, un worktree
s'imbrique en `frontend/.claude/worktrees/<nom>/` — un second dépôt complet, avec
son propre `frontend/` et `backend/`, à l'intérieur du premier. Les trois
configurations qui doivent l'ignorer sont désormais dé-ancrées
(`**/.claude/worktrees/` dans `.gitignore`, `**/.claude/**` dans
`frontend/vitest.config.ts` et `frontend/eslint.config.mjs`), parce qu'aucune ne
le couvrait : `npm test` collectait **52 fichiers de test d'un worktree imbriqué**
en plus des 69 du front, et un `npm test` vert ne disait plus ce qu'on croyait
(#300). Les motifs restent des filets de sécurité — la bonne pratique est de
créer le worktree depuis la racine.

**`EnterWorktree` ne crée rien depuis un worktree** (constaté le 18/08/2026) :
appelé dans une session déjà entrée dans un worktree, il refuse — « Already in a
worktree session. Pass `path` to switch into another existing worktree, or use
ExitWorktree to leave this one before creating a new worktree. » `ExitWorktree`
n'est pas cette issue de secours : il ne gère que les worktrees créés par
`EnterWorktree` **dans la session courante**, et reste un no-op quand la session
a *démarré* dans un worktree (`claude --worktree`, reprise d'un worktree
existant) — il signale qu'aucune session de worktree n'est active, sans rien
changer. Enchaîner une seconde issue laisse donc deux chemins : **une nouvelle
session ouverte depuis la racine**, ou un worktree créé à la main
(`git worktree add -b <branche> .claude/worktrees/<nom> origin/main`) puis
rejoint par `EnterWorktree` avec `path` — seul appel qui passe depuis un
worktree. Le chemin manuel paie le prix décrit juste après : rien de gitignoré
n'est recopié, donc ni `backend/.env` ni base de dev. Indolore pour une
modification de documentation, bloquant pour une tâche backend, qui ne
démarrerait pas.

Un worktree reste une copie **neuve** : rien de gitignoré ne l'accompagne. Pour les
worktrees créés par Claude Code (`claude --worktree`, sous-agents
`isolation: worktree`) ou par Orca, `.worktreeinclude` à la racine liste ce qui doit
suivre — un fichier n'est copié que s'il est à la fois listé **et** gitignoré.
Aujourd'hui : `.env` **et** `backend/.env` (porteur de `DATABASE_URL`), les trois
profondeurs de `.env.local` (racine, `backend/`, `frontend/` — aucune n'existe
aujourd'hui, elles sont listées par avance) et la base de dev
`backend/triathlon.db`.

**Ce sont des chemins littéraux, pas des motifs `.gitignore`** : Orca ne fait aucune
expansion (globs et négations sautés avec un avertissement), donc `.env` seul désigne
le `.env` de la **racine** et rien d'autre. C'est ce qui a fait qu'un worktree Orca
démarrait sans `backend/.env` alors que le fichier semblait couvert : le `.env` racine
existant bel et bien, la copie réussissait — sur le mauvais fichier. Et un chemin
absent est sauté **en silence**, ce qui rend l'entrée morte indiscernable de l'entrée
qui fonctionne.

`frontend/node_modules` n'y figure **pas** : la copie a été essayée puis retirée
de `.worktreeinclude`, parce qu'elle perdait `node_modules/.bin/` (les liens
symboliques vers `vitest`, `eslint`, `next`) — le mécanisme de copie du harnais
saute ce que la copie ne sait pas reconstituer, et le remède le plus immédiat,
`npm install`, réécrit `package-lock.json` au passage. On paie alors la copie
**et** l'installation, ce qui invalide l'arbitrage temps qui avait justifié
l'entrée. Un worktree frontend démarre donc sans `node_modules` : `npm ci` (ou
`npm install`) y est requis avant tout `npm run dev|test|lint|build`. Détail et
mesures : issue #337.

`backend/.venv/` en est absent pour une raison différente, mesurée de même :
2,0 s de copie contre **0,21 s** d'`uv sync`, qui reconstruit l'environnement par
liens durs depuis `~/.cache/uv` — et un venv n'est pas déplaçable, les shebangs de
`.venv/bin/*` portant le chemin absolu du dépôt principal. Ne pas l'ajouter « par
symétrie ».

Deux fichiers en sont exclus pour une troisième raison, la même pour les deux : ils
désignent un worktree **en particulier**. `.dev-backend.json`, que chaque
`dev_server.py` republie, et tout `BACKEND_URL` / `API_URL` figé dans
`frontend/.env.local`, qui brancherait le front d'un worktree sur la base d'un
autre. Un worktree créé à la main (`git worktree add`) ne passe pas par ce
mécanisme : les fichiers sont à copier soi-même.

