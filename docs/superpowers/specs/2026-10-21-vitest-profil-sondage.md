# Sondage : profil vitest, `isolate: false` et happy-dom (#1713)

Mesuré le 21/10/2026 sur `840d3885`, vitest 5.0.2, happy-dom 21.0.4 (installé
`--no-save`, ni `package.json` ni `package-lock.json` touchés). Machine : 8
coeurs, 31 Go de RAM, 16 Go de swap. Suite frontend complète : 326 fichiers,
3700 tests (785 dans le projet `node`, 2915 dans `jsdom`), 2 ignorés.

Les variantes passent par une config jetable non commitée qui importe
`vitest.config.ts` et ne change qu'une option : `vitest.config.ts` n'a pas
bougé.

**Conditions.** Aucune fenêtre au repos : quatre à cinq autres sessions
tournaient (pytest, tsc, vitest d'autres worktrees), load de 9 à 37, swap
plein (14 à 16 Go sur 16) pendant une partie des mesures. Les durées absolues
sont gonflées et varient du simple au triple pour une même variante ; seules
les comparaisons entre bras **entrelacés** (A, B, A, B) se lisent. Les nombres
de tests passés, eux, sont stables d'une exécution à l'autre.

## Profil

`npx vitest doctor` existe en 5.0.2 et rejoue la suite sous plusieurs
configurations (1 exécution chacune, load 12 à 28) :

| Configuration | Résultat |
| --- | --- |
| base (`forks`, `isolate: true`) | 144,1 s |
| `pool: 'threads'` | 255,2 s (+77 %) |
| `pool: 'vmThreads'`, `'vmForks'` | échec : `app/icon.test.ts` « Invalid URL » |
| `isolate: false` (les **deux** projets) | échec : `act()` qui se chevauchent dans `ImportStreamProvider.test.tsx`, exécution tuée à 576 s |
| `fsModuleCache: true` | échec : délai `findBy*` dans `AthleteHeaderActions.test.tsx` |

Sa recommandation : garder la configuration actuelle.

Ventilation de la ligne `Duration` sur la suite complète (base) : tests 37 à
53 %, environment 27 à 38 %, import 10 à 12 %, setup 6 à 10 %, transform 3 %.
jsdom et les imports pèsent toujours ~45 à 50 %, comme au constat de l'epic.

Projet `node` seul : **setup 60 à 69 %** de sa durée. `test/setup.ts` charge
`@testing-library/jest-dom` et `@testing-library/react` pour chacun des
fichiers `node`, qui n'en ont pas besoin, et l'isolation le refait à chaque
fichier.

## Essai 1 : `isolate: false` sur le projet `node` seul

| Workers | Bras | Durées (`Duration`) | Tests | RSS crête par worker |
| --- | --- | --- | --- | --- |
| défaut (7) | base | 11,2 s, 11,1 s, 17,9 s | 785 verts | non relevé |
| défaut (7) | `isolate: false` | 3,7 s, 4,4 s, 5,0 s | 785 verts | non relevé |
| 3 | base | 61,3 s, 39,7 s | 785 verts | 148 Mi, 110 Mi |
| 3 | `isolate: false` | 11,3 s, 8,6 s | 785 verts | 224 Mi, 198 Mi |

Projet `node` 3 à 5 fois plus rapide, 785 verts dans les cinq exécutions, et
le `setup` retombe de ~65 % à ~20 % de la durée. Coût : le RSS crête d'un
worker `node` passe de ~130 à ~210 Mi, toujours loin d'un worker jsdom.

Suite complète, 3 workers, bras entrelacés :

| Bras | Exécution | load au départ | Duration | Tests |
| --- | --- | --- | --- | --- |
| base | 1 | 31,6 | 256,0 s | 3698 verts |
| `isolate: false` | 1 | 8,8 | 171,7 s | 3698 verts |
| base | 2 | 9,4 | 184,0 s | 3698 verts |
| `isolate: false` | 2 | 9,2 | 213,2 s | 3698 verts |

Sur la suite complète, le gain du projet `node` (~7 à 40 s selon la charge)
se noie dans le bruit : jsdom fait l'essentiel de la durée. Aucun test cassé.
L'échec du doctor vient de `isolate: false` appliqué **aussi** à `jsdom`, pas
de l'option mesurée ici.

## Essai 2 : happy-dom sur le projet `jsdom`

Suite complète, 3 workers :

| Bras | Exécution | Duration | Tests | RSS crête par worker | RSS crête total |
| --- | --- | --- | --- | --- | --- |
| jsdom (base) | 2 | 184,0 s | 3698 verts | 555 Mi | 1223 Mi |
| happy-dom | 1 | 132,7 s | 33 rouges, 3648 verts, 17 non collectés | 394 Mi | 893 Mi |
| happy-dom | 2 | 152,9 s | idem, mêmes tests | 389 Mi | 966 Mi |

happy-dom est ~20 à 28 % plus rapide et ~30 % plus léger par worker, mais
**casse 33 tests dans 18 fichiers, et 2 fichiers ne se chargent plus**, à
l'identique sur les deux exécutions (déterministe, pas de la charge) :

| Cause | Fichiers |
| --- | --- |
| `navigator.clipboard` en lecture seule, le fichier ne se charge pas (17 tests non collectés) | `BenevoleAccessConfig`, `SiteAccessConfig` |
| Styles en ligne sérialisés autrement (`toHaveStyle`, `'0'` contre `'0px'`, `#fff` contre `rgb(...)`, raccourcis `border` éclatés) | `AccountPage`, `AppNav`, `SpaceSwitcher`, `ColonneDroite`, `AthletePicker`, `TcnScrapeForm`, `FeedbackButton`, `LigneCarte`, `SegmentedControl`, `ComparisonTable` |
| Cookies : expiration non appliquée | `lib/analytics-consent.test.ts` |
| `clientWidth` absent, SVG lu à `null` | `StatCard`, `RankingEvolutionChart` |
| Nom accessible d'un lien, nonce CSP, état de bascule, méthode absente pour `vi.spyOn` | `blocks`, `StableCSPProvider`, `RankTypeToggle`, `OngletDisciplines`, `GroupDetailDialog` |

Une bascule demanderait de réécrire ces assertions (surtout celles de style),
c'est une migration, pas une option de config.

## Workers et mémoire

`vitest.config.ts` ne pose aucun `maxWorkers` : vitest prend coeurs - 1, soit
**7 workers** sur cette machine. Un worker jsdom monte à **~555 Mi** de RSS
crête (relevé à la seconde sur les quatre exécutions jsdom à 3 workers) : une
suite complète au défaut tient donc ~3,5 à 4 Go, et chaque worktree qui lance
la sienne en même temps les ajoute. C'est ce qui a rempli le swap (16 Go sur
16) pendant ce sondage, avec quatre sessions actives : l'orchestrateur a fait
arrêter la série à 7 workers.

À 3 workers, la suite complète tient 1,2 Go (jsdom) et dure 172 à 256 s à load
9 à 32, contre 139 à 144 s à 7 workers et load 12. Le plafond coûte du temps
mural sur une machine libre ; il en fait gagner dès que plusieurs suites se
partagent les coeurs.

## Recommandation

1. **`isolate: false` sur le projet `node`** : gain net (3 à 5 fois sur ce
   projet, ~7 s par suite), 785 verts dans les sept exécutions, au prix de
   ~80 Mi par worker `node`. À appliquer dans une issue à part, ses tests verts
   en CI, hors du gel v0.9.0 : la consigne de cette issue est de ne pas toucher
   la config de test (risque CI).
2. **Plafond de workers en local** : `maxWorkers: 3` (ou `"40%"`), seulement
   hors CI (`process.env.CI`), pour ne rien changer au runner de la CI. Même
   suite à part que le point 1.
3. **happy-dom : non.** Gain réel mais 33 tests cassés et 2 fichiers qui ne se
   chargent plus. À rouvrir seulement si le coût d'environnement redevient le
   premier poste, avec une migration des assertions de style budgétée.
4. Hors périmètre relevé au passage : `test/setup.ts` charge Testing Library
   pour les fichiers `node`. Le garder sous `typeof document !== "undefined"`
   ou un `setupFiles` propre à `jsdom` réduirait le `setup` du projet `node`
   même avec isolation.
