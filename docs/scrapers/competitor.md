# Competitor (IRONMAN / 70.3)

**Competitor** (#54) est le moteur réel derrière `ironman.com` — d'où le nom du
provider — commun à toutes les épreuves IRONMAN / 70.3. La page « Results »
encastre une iframe `labs-v2.competitor.com` (Next.js, `__NEXT_DATA__`) : deux
sauts, page → uuid → JSON. Trois particularités structurantes :

- **une URL désigne une série, pas une édition** (21 éditions pour IRONMAN
  France) et le site n'expose aucune URL par année. On importe la dernière
  édition publiée — sauf si l'uuid de l'URL est lui-même celui d'une édition,
  auquel cas c'est celle-là. Cela donne un rattrapage par année que le site
  n'offre pas ;
- **`latestResults` de la page est amputé de l'Open Division** (62 athlètes sur
  1810 à IRONMAN France 2025) : on ne le réutilise jamais, le classement est
  redemandé au proxy `labs-v2.competitor.com/api/results-proxy?url=…` sans
  filtre de catégorie. `api.competitor.com` n'est **pas** joignable en direct
  (401, clé APIM) et le proxy n'accepte que `/web/results` ;
- **la source ne publie aucun club** : une participation Competitor sort avec
  `club = ""` et n'est donc jamais marquée TCN. Limite assumée, pas un bug.

Pièges à ne pas réintroduire : `wtc_swimtime_formatted` (secondes) n'est pas
`wtc_swimtimeformatted` (durée) ; `wtc_ContactId.gendercode` est faux (77 lignes
sur 1585 mesurées) — le genre se lit sur la catégorie d'âge ; `athlete`/`bib`
sont fabriqués côté navigateur et absents des réponses du proxy.
Sondage (source de vérité, 7 épreuves) :
`docs/superpowers/specs/2026-07-26-competitor-ironman-sondage.md`.
Design : `docs/superpowers/specs/2026-07-26-competitor-ironman-design.md`.
