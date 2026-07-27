# Research — Skill « onboard »

Ce document consolide les décisions du Phase 0 du plan
(`plan.md` §Phase 0). Chaque section suit le format
**Décision / Rationale / Alternatives**.

## D1 — Structure du SKILL.md

**Décision** : un unique `SKILL.md` avec frontmatter YAML, corps en
Markdown, imports de ressources annexes via mentions explicites du chemin
(`Lis .claude/skills/onboard/references/tour-backend.md`).

**Rationale** : c'est exactement le patron des skills `speckit-*` déjà
présents dans `.claude/skills/`. Contributeur qui ouvre le dossier
retrouve la structure familière. Le format Markdown reste lisible pour un
humain qui ne connaît pas Claude Code.

**Alternatives considérées** :
- Skill + script bash externalisé — rejeté (couche shell à maintenir en
  synchro).
- SKILL.md mono-fichier de ~800 lignes — rejeté (illisible en revue).

## D2 — Format du `state.json`

**Décision** : JSON plat, minimal, versionné par `schema_version`. Une clé
par étape (`step_prerequisites`, `step_install`, `step_db`, `step_tests`,
`step_dev`, `step_tour`, `step_ia_tooling`, `step_first_feature`), valeur
`"pending" | "done" | "skipped" | "failed"`. Réponses aux questions
initiales dans un sous-objet `answers`. Timestamp `last_updated` en ISO
8601 UTC.

**Rationale** : simple, lisible avec `jq`, permet la reprise granulaire.
`schema_version` protège d'un rejeu sur un state issu d'une version
antérieure du skill (le skill invalide et redemande).

**Alternatives considérées** :
- YAML — rejeté (dépendance côté script si on veut lire le state hors
  skill ; JSON + `jq` suffit).
- Pas de `schema_version` — rejeté (empêche toute évolution ultérieure du
  format).
- Un fichier par étape (`step_install.done`) — rejeté (multiplie les
  fichiers pour un gain nul).

## D3 — Détection de l'état d'installation

**Décision** : commandes shell rapides au démarrage, combinées au state
persisté. Le state est **autorité déclarative** (« j'ai répondu que je
voulais SQLite »), la détection est **autorité factuelle** (« le venv
existe »). En cas de désaccord (state=`done` mais artefact absent), la
détection l'emporte et l'étape est rejouée.

**Rationale** : le state seul mentirait après un `rm -rf .venv`. La
détection seule ne connaît pas les réponses du contributeur.

**Sondes** : `[ -f backend/.env ]`, `[ -d backend/.venv ]`, `[ -d
frontend/node_modules ]`, `[ -f backend/triathlon.db ]` + `stat -c%s`
minimum 100 Ko, `curl -sSo /dev/null -w '%{http_code}' http://localhost:8001/docs`
et idem sur `:3000`.

**Alternatives considérées** :
- Se fier au state seul — rejeté (drift silencieux).
- Se fier à la détection seule — rejeté (le skill oublie les choix du
  contributeur à chaque relance).

## D4 — Stratégie pour `gh` absent / non authentifié (FR-015)

**Décision** : trois branches déterministes :

1. **`gh` absent** (`command -v gh` échoue) → afficher la commande
   d'install officielle Ubuntu/macOS, proposer de skipper, retomber sur
   le fallback texte de FR-015.
2. **`gh` présent mais non authentifié** (`gh auth status` code ≠ 0) →
   proposer `gh auth login`, avec les deux options (web browser, ou
   skip).
3. **`gh issue list ... --json` échoue** pour toute autre raison
   (réseau, rate limit, label absent) → afficher l'erreur brute et
   fallback texte manuel.

**Rationale** : chaque branche est testable dans `quickstart.md`
(désinstaller `gh`, révoquer le token, couper le réseau). Aucune branche
cachée qui ne serait pas vérifiable.

**Alternatives considérées** :
- API GitHub via `curl` : rejeté (complexité, gestion de token à
  réimplémenter).
- Ignorer FR-015 si `gh` absent : rejeté (contredit l'objectif du skill).
- Utiliser le MCP GitHub (déjà configuré dans `.mcp.json`) : rejeté à ce
  stade — le MCP nécessite une session Claude Code active *et* configurée,
  ce qui est le cas dans notre contexte de test mais pas garanti pour un
  contributeur qui utilise un autre client MCP. `gh` est plus universel.

## D5 — Emplacement du `state.json` dans le `.gitignore`

**Décision** : ajouter la ligne `.claude/skills/onboard/state.json` au
`.gitignore` racine. Ne pas ignorer le répertoire entier.

**Rationale** : granularité minimale. Le corps du skill (SKILL.md,
references) DOIT être commité. Un contributeur qui souhaite partager son
état d'onboarding (support, débogage) peut le forcer avec `git add -f`.

**Alternatives considérées** :
- Ignorer `.claude/skills/onboard/` entier — rejeté (empêche de commiter
  le skill lui-même).
- Stocker dans `/tmp/onboard-state.json` — rejeté (perdu au reboot ; ne
  survit pas à un `WSL --shutdown`).
- Stocker dans `~/.config/tcn/onboard-state.json` — rejeté (le skill est
  projet-spécifique ; le state doit vivre avec le repo).
