# RTK — compresser la sortie des commandes

[RTK](https://github.com/rtk-ai/rtk) (« Rust Token Killer », Apache-2.0) est un
**proxy CLI** : `rtk <commande>` exécute la commande réelle, puis n'en restitue
que l'essentiel. Le code de sortie et le comportement de la commande sont
inchangés ; seule la sortie affichée rétrécit. Un binaire Rust unique, sans
dépendance, moins de 10 ms de surcoût.

L'intérêt ici est étroit mais massif : **`uv run pytest` est de loin la commande
la plus coûteuse en contexte de ce dépôt**, et c'est celle que RTK écrase le
mieux.

## Ce que ça rapporte vraiment, mesuré sur ce dépôt

Mesuré le 21/08/2026 avec rtk 0.45.0, en octets de sortie, sur la branche de
l'issue #519. Les chiffres du README amont (« -60 à -90 % partout ») ne se
vérifient pas ici : le gain est **concentré**, et nul là où l'outil est déjà
concis.

| Commande | Brut | Avec `rtk` | Gain |
| --- | --- | --- | --- |
| `uv run pytest -m "not integration"` | 404 510 o | 4 374 o | **-98,9 %** |
| `uv run pytest -m "not integration" -q` | 15 930 o | 3 715 o | -77 % |
| `gh run list --limit 20` | 2 654 o | 641 o | -76 % |
| `git log -20` | 11 766 o | 4 850 o | -59 % |
| `gh pr list --limit 20` | 1 751 o | 1 205 o | -31 % |
| `npm run build` (Next.js) | 6 777 o | 6 741 o | ~0 |
| `npx vitest run lib` (vert) | 272 o | 268 o | ~0 |
| `uv run ruff check .` (vert) | 19 o | 19 o | 0 |

Trois enseignements, qui décident de l'usage :

1. **Préfixer `uv run pytest` est le seul geste à retenir absolument.** 400 ko
   de points et de `SAWarning` deviennent 4 ko, et la ligne qui sert de preuve
   (`3656 passed, 74 deselected`) est conservée telle quelle.
2. **Vitest, ESLint, ruff et `next build` n'ont rien à y gagner** : ils sont déjà
   compacts quand ils passent. Préfixer ne nuit pas, mais ne sert à rien.
3. **Sur une suite en échec, le gain s'effondre** : RTK réduit les passages, pas
   les échecs, dont il garde le détail intégral. C'est le comportement voulu —
   mais ne pas s'attendre à -99 % quand ça casse.

## Installation

RTK est **optionnel** : le dépôt fonctionne à l'identique sans lui, et rien dans
la CI n'en dépend. Il n'est ni dans `uv.lock` ni dans `package-lock.json` — c'est
un outil de poste de travail, pas une dépendance du projet.

```bash
# 1. Vérifier qu'on n'a pas déjà le mauvais « rtk » (voir ci-dessous)
rtk gain

# 2. Installer (le script vérifie le SHA-256 et refuse une archive à chemins douteux)
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh -o /tmp/rtk-install.sh
sh /tmp/rtk-install.sh          # → ~/.local/bin/rtk

# 3. Vérifier
rtk --version                   # rtk 0.45.0
rtk gain                        # doit afficher le tableau d'économies
```

Le `.claude/settings.json` du dépôt autorise déjà `Bash(rtk*)`, et il **refuse**
`Bash(curl * | sh*)` : télécharger le script puis le lancer n'est pas une
coquetterie, c'est la seule forme permise — et elle laisse le script relisible
avant exécution.

Si `rtk: command not found`, ajouter à `~/.zshrc` :

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Le piège de l'homonymie

**Deux projets distincts s'appellent `rtk`.** « Rust Token Killer » (celui-ci)
n'a rien à voir avec « Rust Type Kit », un outil d'interrogation de code. Le seul
test fiable est `rtk gain` : il doit afficher un tableau d'économies (ou « No
tracking data yet »), pas une erreur de commande inconnue. En cas d'erreur :

```bash
cargo uninstall rtk 2>/dev/null
# puis reprendre l'installation ci-dessus
```

## Portée retenue : projet, sans hook

RTK propose deux modes, et **nous n'en prenons qu'un**.

- **Mode projet (retenu)** — les instructions vivent dans le dépôt, l'agent
  préfixe `rtk` lui-même. Rien n'est modifié en dehors du dépôt.
- **Mode global (`rtk init -g`, écarté par défaut)** — installe
  `~/.claude/hooks/rtk-rewrite.sh` et patche `~/.claude/settings.json` pour
  réécrire **toute** commande Bash, de façon transparente et dans tous les
  projets du poste. C'est plus confortable, mais c'est une décision de poste de
  travail, pas de dépôt : elle ne se prend pas dans une PR.

À savoir avant d'y toucher : dans rtk 0.45, **le hook de réécriture n'existe
qu'en mode global**. `rtk init --hook-only` sans `-g` est refusé par l'outil. Il
n'y a donc pas de hook borné à un seul dépôt à installer ici, et
`.claude/settings.json` n'a pas été patché.

Autre raison d'avoir écarté le mode par défaut de `rtk init` : il injecte
**140 lignes d'anglais dans `CLAUDE.md`** — catalogue de `cargo`, `go test`,
`rspec`, `prisma`, `kubectl`, tout hors de notre stack — alors que la convention
du dépôt veut un `CLAUDE.md` d'une ligne (`@AGENTS.md`) et un contexte racine
sous 200 lignes. Cette page remplace ce catalogue par les six commandes qui nous
concernent. Si `rtk init` est relancé par erreur :

```bash
git checkout -- CLAUDE.md
```

## Les commandes qui valent le préfixe

Uniquement celles de notre `## Commandes` où le gain est mesuré :

```bash
# Backend (depuis backend/) — le gain est ici
rtk uv run pytest -m "not integration"    # -98,9 % : le geste à retenir
rtk uv run pytest -m integration          # idem sur les tests réseau

# Dépôt
rtk git log -20                           # -59 %
rtk gh run list                           # -76 %, utile pour surveiller la CI
rtk gh pr view <num>                      # sortie de PR compactée
```

Le préfixe n'est **jamais dangereux** : sans filtre dédié, RTK passe la commande
telle quelle. Dans une chaîne, chaque maillon se préfixe séparément
(`rtk git add . && rtk git commit -m "..."`), sinon seul le premier est filtré.

## Garde-fous — non négociables

Ce dépôt fait de la sortie de commande une **preuve** :
`verification-before-completion` interdit d'annoncer un succès sans l'avoir
constaté, et un sondage terrain prime sur le plan (`AGENTS.md`, § Workflow IA).
RTK tronque. Les deux se concilient, à trois conditions.

1. **La sortie complète n'est jamais perdue.** RTK la conserve sur disque et en
   donne le chemin en fin de sortie (`~/.local/share/rtk/tee/…`). Une preuve qui
   porte sur ce qui a été retiré se relit là, ou se refait en brut.
2. **Un sondage ou un audit se fait en commande brute.** Tout ce qui alimente
   `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md` est une
   mesure de terrain : elle se fait sans filtre, ou elle ne vaut rien. Idem pour
   `systematic-debugging`, où le symptôme est souvent précisément la ligne qu'un
   filtre juge accessoire.
3. **Ne jamais préfixer une commande dont on lit la sortie ligne à ligne.** La
   CLI de batch (`backend/app/cli/`) a un stdout *parsable* et des codes de
   sortie contractuels (`backend/app/cli/AGENTS.md`) : la compresser casse le
   contrat. Même règle pour `alembic upgrade head` et les scripts de `scripts/`.

En pratique : `rtk` sur les commandes qu'on lit pour **décider** (les tests
passent-ils ? la CI est-elle verte ?), brut sur les commandes qu'on lit pour
**comprendre** ou dont la sortie est consommée par un outil.

## Configuration

- **`.rtk/filters.toml`** (dans le dépôt, versionné) — filtres propres au projet.
  Aujourd'hui un gabarit vide de tout filtre actif : aucun n'a fait ses preuves
  ici, et un filtre maison qui masque une ligne utile coûte plus qu'il ne
  rapporte. À remplir seulement sur un besoin mesuré.
- **`~/.config/rtk/config.toml`** (poste de travail, hors dépôt) — utile surtout
  si le hook global est installé un jour, pour en exclure les commandes de
  mesure :

  ```toml
  [hooks]
  exclude_commands = ["curl", "alembic", "python -m app.cli"]
  ```

## Désinstaller

```bash
rtk init --uninstall     # retire les artefacts RTK du dépôt courant
rm ~/.local/bin/rtk      # retire le binaire
```

Rien d'autre à défaire : aucun fichier de `~/.claude/` n'a été modifié, et le
dépôt ne dépend pas de RTK.
