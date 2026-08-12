export const meta = {
  name: '195-fanout-scrapers',
  description: 'Épique #195 — 6 scrapers migrent en parallèle vers le patron fan-out Klikego. Un agent par scraper, chacun dans un worktree isolé, PR interne vers la branche parapluie feat/195-cache-ttl-fanout-scrapers.',
  whenToUse: 'Quand la branche parapluie feat/195-cache-ttl-fanout-scrapers existe côté origin et que les 6 sub-issues (#216-#221) sont ouvertes. Lance 6 agents en parallèle, chacun implémente une sub-issue et pousse sa PR vers la parapluie.',
  phases: [
    { title: 'Fan-out — implémentation des 6 scrapers', detail: 'un agent par sub-issue, worktree isolé, PR interne' },
    { title: 'Bilan', detail: 'récap des 6 PR à orchestrer côté humain' },
  ],
}

const KLIKEGO_PATRON = `
# Patron fan-out Klikego — contrats à respecter

Références réelles à lire AVANT de coder :
- \`backend/app/scrapers/klikego.py\` — signature \`scrape_event_fanout\`, \`FanoutTrace\`, \`_heat_source_url\`, \`_enumerate_heats\`, isolation d'échec par heat.
- \`backend/app/services/import_service.py\` — \`_make_cache_probe\`, \`_fanout_counters\`, \`_merge_cached_courses\`, chemin SSE streaming (\`_scrape_all_streaming\`).
- \`backend/tests/test_klikego.py\` — 5 scénarios de fan-out (nominal, cache_probe skip, échec isolé, aucune sous-unité, on_heat_start non-notifié pour cachées).
- \`backend/tests/test_services/test_import_service.py\` — compteurs done, invariant, réhydratation.

Contrats non négociables :
1. **\`FanoutTrace(heats_enumerated, heats_cached, heats_imported=0, failures, cached_urls)\`** — dataclass à 5 champs. \`heats_imported\` reste à 0 côté scraper : dérivé par \`import_service._fanout_counters\` via l'invariant \`enumerated = imported + cached + len(failures)\`.
2. **Provider expose \`scrape_event_fanout(...)\`** avec la même forme que Klikego :
   \`\`\`python
   def scrape_event_fanout(
       *args,
       cache_probe: Callable[[str], bool] | None = None,
       on_heat_start: Callable[[str, str, int, int], None] | None = None,
   ) -> tuple[list[ScrapedResult], FanoutTrace]:
   \`\`\`
   Le \`Provider\` (classe dans \`registry.py\`) reçoit \`cache_probe\` et \`on_heat_start\` en kwargs et stocke \`self.last_trace\` — comme \`KlikegoProvider\`.
3. **\`scrape_event_all(...)\` mono-sous-unité conservé** pour l'échappatoire \`--single-heat\` et les tests unitaires. Sa signature d'origine ne change pas.
4. **URL canonique de sous-unité** — une seule fonction dans le module (\`_sub_source_url\` ou nommage local), employée simultanément comme :
   - clé de cache TTL (\`cache_probe\` reçoit exactement cette URL),
   - valeur de \`ScrapedResult.source_url\` (persistée en \`Course.source_url\`).
5. **\`cache_probe(sub_url) -> bool\`** invoqué **AVANT** la requête réseau. Une sous-unité fraîche :
   - incrémente \`trace.heats_cached\`,
   - est ajoutée à \`trace.cached_urls\`,
   - N'EST PAS notifiée à \`on_heat_start\`,
   - N'est ni scrapée ni construite en \`ScrapedResult\`.
6. **\`on_heat_start(slug, label, index, total)\`** — \`total = len(à_scraper)\`, PAS le total absolu. Sans quoi la progression sauterait des indices sur un ré-import majoritairement caché.
7. **Isolation d'échec par sous-unité** — try/except autour du traitement d'une sous-unité, log warning, \`trace.failures.append({..., "reason": str(exc)})\`. Les autres sous-unités continuent.
8. **\`registry.py\`** : le \`Provider\` correspondant expose \`scrape_event_all(url, ..., cache_probe=None, on_heat_start=None, single_heat=False)\` qui délègue à \`scrape_event_fanout\` en mode normal, et à \`scrape_event_all\` du module en mode \`--single-heat\`. Stocke \`self.last_trace = trace\`.

Tests à répliquer (5 scénarios minimum) :
- **Nominal** : 3 sous-unités énumérées, 3 scrapées, \`FanoutTrace(3, 0, imported dérivé=3, [], [])\`.
- **cache_probe skip** : 1 sous-unité déjà fraîche → \`heats_cached=1\`, \`cached_urls=[<url>]\`, \`on_heat_start\` NON notifié pour cette sous-unité, 2 autres scrapées.
- **Échec isolé** : 1 sous-unité lève, les 2 autres passent → \`trace.failures\` contient 1 entrée, \`heats_imported dérivé=2\`.
- **Aucune sous-unité** : source à zéro entrée → \`FanoutTrace(0, 0, 0, [], [])\`, aucune erreur.
- **on_heat_start non-notifié pour les cachées** : \`total\` reçu par on_heat_start = nombre à scraper, pas nombre énuméré.
`

const SUB_ISSUES = [
  {
    number: 216,
    scraper: 'sporthive',
    branchName: 'feat/195-sporthive',
    label: 'Sporthive',
    subUnit: 'race',
    file: 'backend/app/scrapers/sporthive.py',
    tests: 'backend/tests/test_sporthive.py',
    keyPoint: `Sous-unité = **race** de l'event Sporthive, id = \`race.id\` **snowflake 19 chiffres** — PAS l'ordinal \`activeRaceId\`. Piège documenté déjà dans le docstring. URL canonique : \`…/events/{eventId}/races/{raceId}\` (snowflake). Boucle \`for race in _fetch_races(...)\` dans sporthive.py:603 — poser cache_probe AVANT premier \`_iter_participants\` (skip ~100 requêtes de pagination), on_heat_start juste avant \`_scrape_race\`. Préserver : refus double (race incomplète = drop, event vide = raise).`,
  },
  {
    number: 217,
    scraper: 'raceresult',
    branchName: 'feat/195-raceresult',
    label: 'RaceResult',
    subUnit: 'contest',
    file: 'backend/app/scrapers/raceresult.py',
    tests: 'backend/tests/test_raceresult.py',
    keyPoint: `Sous-unité = **contest** de \`config["contests"]\`, indexé par contest_id numérique. Un contest peut être couvert par plusieurs listes RaceResult (fusion \`(contest_label, bib)\` déjà en place). URL canonique : \`…/{eventId}/results?contest={contestId}\`. \`Contest="0"\` (« toutes catégories ») est **exclu** du fan-out — cas particulier réservé, pas cache-able. Boucle \`for contest, payload, groupes in recuperees\` dans raceresult.py:1388. Les listes \`hidden\` restent liées à leur contest et suivent le cache du contest.`,
  },
  {
    number: 218,
    scraper: 'chronoplace',
    branchName: 'feat/195-chronoplace',
    label: 'Chronoplace',
    subUnit: 'épreuve',
    file: 'backend/app/scrapers/chronoplace.py',
    tests: 'backend/tests/test_chronoplace.py',
    keyPoint: `Sous-unité = **épreuve** (\`epreuve_id\` numérique). URL canonique déjà bien nommée : \`_epreuve_path(slug, epreuve_id)\` → \`/classement/<slug>/epreuve/<id>?perPage=all\`. Boucle \`for sibling in _list_epreuves(...)\` dans chronoplace.py:482. **Attention** : la date d'événement est fetch UNE SEULE FOIS en amont (chronoplace.py:475) — elle n'est PAS propre à une sous-unité, ne pas la déplacer dans la boucle.`,
  },
  {
    number: 219,
    scraper: 'wiclax',
    branchName: 'feat/195-wiclax',
    label: 'Wiclax/G-Live',
    subUnit: 'parcours',
    file: 'backend/app/scrapers/wiclax.py',
    tests: 'backend/tests/test_wiclax.py',
    keyPoint: `Sous-unité = **parcours** (attribut \`p\` du XML \`.clax\`). Le \`.clax\` est PARTAGÉ par tous les parcours — une seule requête réseau. Le gain n'est pas la requête économisée mais **l'intégrité du cache TTL**. URL canonique à concevoir : \`<url>&parcours=<slug>\` (attention : \`p=\` est déjà dans le XML, pas dans l'URL entrante — conflit à éviter). Pré-groupe \`by_parcours\` existe déjà (wiclax.py:355). \`cache_probe\` peut skipper la CONSTRUCTION des ScrapedResult d'un parcours frais, pas la requête. À documenter dans la docstring.`,
  },
  {
    number: 220,
    scraper: 'chronoweb',
    branchName: 'feat/195-chronoweb',
    label: 'Chronoweb',
    subUnit: 'race',
    file: 'backend/app/scrapers/chronoweb.py',
    tests: 'backend/tests/test_chronoweb.py',
    keyPoint: `Sous-unité = **race**, \`race.race_id\` lu depuis \`<select class="select_epreuve">\`. UNE SEULE requête HTML pour tout l'événement. Le gain n'est pas la requête économisée mais **l'intégrité du cache TTL**. URL canonique recommandée : \`<canonical_url>&race=<race_id>\` (query, cohérente avec Klikego \`?heat=…\`). Boucle \`for race in _parse_races(soup, meta)\` dans chronoweb.py:517.`,
  },
  {
    number: 221,
    scraper: 'oktime',
    branchName: 'feat/195-oktime',
    label: 'ok-time',
    subUnit: 'course',
    file: 'backend/app/scrapers/oktime.py',
    tests: 'backend/tests/test_oktime.py',
    keyPoint: `Sous-unité = **course** de la charge JSON (\`charge["data"]\`), identifiée par \`epreuve_id\`. UN SEUL GET rend tout l'événement (comme Chronoweb). Le gain n'est pas la requête économisée mais **l'intégrité du cache TTL**. URL canonique DÉJÀ acceptée par \`_ID_PATH_RE\` (oktime.py:51) : \`classement.ok-time.fr/<id>/race/<epreuveId>\`. Boucle \`for course in charge.get("data")\` dans oktime.py:680.`,
  },
]

phase('Fan-out — implémentation des 6 scrapers')
log(`Fan-out de ${SUB_ISSUES.length} agents — un par scraper, chacun en worktree isolé`)

const RUNS = await parallel(
  SUB_ISSUES.map((sub) => () =>
    agent(
      `Tu implémentes la sub-issue #${sub.number} de l'épique #195 — migration du scraper **${sub.label}** vers le patron fan-out Klikego.

## Contexte

Tu opères sur le dépôt data-triathlon (backend FastAPI Python + frontend Next.js). Ton objectif : appliquer le patron fan-out Klikego au scraper \`${sub.scraper}\` pour que le cache TTL raisonne par **${sub.subUnit}** au lieu d'événement entier.

## Spécificité de ce scraper

${sub.keyPoint}

## Ce que tu dois lire avant d'écrire une ligne

1. **La sub-issue #${sub.number}** sur GitHub — \`gh issue view ${sub.number} --repo Triathlon-Club-Nantais/data-triathlon\`. Le body porte les contrats et les points de vigilance spécifiques.
2. **L'épique #195** — \`gh issue view 195 --repo Triathlon-Club-Nantais/data-triathlon\`. Contexte global.
3. **Le patron Klikego** — code réel :
   - \`backend/app/scrapers/klikego.py\` (signature \`scrape_event_fanout\`, \`FanoutTrace\`, \`_heat_source_url\`, \`_enumerate_heats\`, isolation d'échec).
   - \`backend/app/scrapers/registry.py\` (comment \`KlikegoProvider\` intègre le fan-out).
   - \`backend/app/services/import_service.py\` (\`_make_cache_probe\`, \`_fanout_counters\`, \`_merge_cached_courses\`).
   - \`backend/tests/test_klikego.py\` (les 5 scénarios de fan-out à répliquer).
4. **Le scraper à modifier** : \`${sub.file}\`.
5. **Sa suite de tests** : \`${sub.tests}\`.

## Setup git — CRITIQUE

Tu es dans un **worktree isolé** (le workflow t'aura créé un). Vérifie ton pwd — tu dois être dans un dossier sous \`.claude/worktrees/\` ou similaire. Ne travaille JAMAIS dans \`/home/mherrmann/work/tcn/data-triathlon\` directement, tu marcherais sur les autres agents.

Ta branche : \`${sub.branchName}\`.

Elle doit être **branchée sur \`feat/195-cache-ttl-fanout-scrapers\` (la parapluie)**, PAS sur main. Commandes :
\`\`\`bash
git fetch origin feat/195-cache-ttl-fanout-scrapers
git checkout -b ${sub.branchName} origin/feat/195-cache-ttl-fanout-scrapers
\`\`\`

## Ce que tu dois faire

${KLIKEGO_PATRON}

## Ta livraison

1. **Code** : modifier \`${sub.file}\` et \`registry.py\` (extension du \`Provider\` correspondant).
2. **Tests** : ajouter dans \`${sub.tests}\` les 5 scénarios de fan-out (nominal, cache_probe skip, échec isolé, aucune sous-unité, on_heat_start non-notifié pour cachées).
3. **Suite de tests verte** :
   \`\`\`bash
   cd backend && uv run pytest -m "not integration" -q
   cd backend && uv run ruff check .
   \`\`\`
4. **Commit + push** : conventional commit, message court, référence \`Refs #${sub.number}\`.
5. **PR interne** vers \`feat/195-cache-ttl-fanout-scrapers\` (PAS vers main). Utilise \`gh pr create --base feat/195-cache-ttl-fanout-scrapers --head ${sub.branchName} --title "..." --body "..."\`.

## Contraintes

- Ne pas toucher à \`services/cache.is_fresh\` ni au TTL — hors périmètre.
- Ne pas purger de \`Course\` en base — la migration éventuelle est un ticket séparé.
- Ne pas changer le comportement de \`scrape_event_all\` mono-sous-unité (rétrocompatibilité tests + \`--single-heat\`).
- Aucune régression sur les scénarios existants du scraper — les tests actuels doivent rester verts.

## Livraison finale (ce que tu retournes en texte)

Un rapport structuré :
- **Statut** : \`SUCCESS\`, \`PARTIAL\` (code écrit mais tests rouges), ou \`FAILED\` (blocage identifié).
- **URL de la PR interne** créée.
- **Résumé de ce qui a changé** : 3-5 lignes.
- **Points de vigilance** rencontrés que le mainteneur doit connaître avant merge de la parapluie.
- **Tests** : compteurs avant/après (X passed, Y failed).`,
      {
        label: `195:${sub.scraper}`,
        phase: 'Fan-out — implémentation des 6 scrapers',
        isolation: 'worktree',
        effort: 'high',
      },
    ),
  ),
)

phase('Bilan')

const results = RUNS.map((r, i) => ({ scraper: SUB_ISSUES[i].scraper, number: SUB_ISSUES[i].number, output: r }))

const success = results.filter((r) => r.output && typeof r.output === 'string')
const failed = results.filter((r) => !r.output)

log(`Terminé : ${success.length}/${SUB_ISSUES.length} agents ont rendu un rapport, ${failed.length} ont échoué en cours de route.`)

return {
  epic: 195,
  parapluie: 'feat/195-cache-ttl-fanout-scrapers',
  agents_terminés: success.length,
  agents_échoués: failed.length,
  détail: results.map((r) => ({
    sub_issue: r.number,
    scraper: r.scraper,
    rapport: r.output ?? '(agent en échec — voir /workflows pour la trace)',
  })),
  prochaine_étape: `Revoir chaque PR interne dans /pulls (base=feat/195-cache-ttl-fanout-scrapers). Une fois les 6 mergées dans la parapluie, ouvrir la PR parapluie → main avec 'Closes #195'.`,
}
