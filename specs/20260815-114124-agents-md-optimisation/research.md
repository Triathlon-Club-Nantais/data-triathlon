# Research: Optimisation des fichiers AGENTS.md avec référence

## Audit de taille — tous les `AGENTS.md`

| Fichier | Lignes | Auto-chargé ? | Verdict |
|---|---|---|---|
| `AGENTS.md` (racine) | 191 | à chaque session | sous son propre seuil (200) — inchangé (sauf ajout volets 2-3) |
| `backend/AGENTS.md` | 34 | lecture d'un fichier `backend/` | conforme |
| `backend/app/core/AGENTS.md` | 60 | lecture d'un fichier `app/core/` | conforme |
| `backend/app/scrapers/AGENTS.md` | 86 | lecture d'un fichier `app/scrapers/` | conforme — **patron de référence déjà en place** (table + `docs/scrapers/<fournisseur>.md`) |
| `frontend/AGENTS.md` | 100 | lecture d'un fichier `frontend/` | conforme |
| `backend/app/models/AGENTS.md` | 192 | lecture d'un fichier `app/models/` | sous le seuil, 3 sujets déjà bien délimités — inchangé |
| `backend/app/cli/AGENTS.md` | 304 | lecture d'un fichier `app/cli/` | au-dessus du seuil mais **un seul sujet cohérent** (la couche CLI et ses 6 commandes), pas une juxtaposition d'epics indépendantes — inchangé |
| `backend/app/services/auth/AGENTS.md` | 486 | lecture d'un fichier `app/services/auth/` | **retenu** — 4 epics indépendantes (#114, #115, #170, #197) sous un même fichier |
| `backend/app/api/AGENTS.md` | 494 | lecture d'un fichier `app/api/` | **retenu** — 13 sections, dont 5 forment une epic détachable (#275 : #284-#287) et 4 sont des gestes d'administration indépendants (#169, #117, #288, #267, #272) |

**Décision** : seuls `backend/app/api/AGENTS.md` et
`backend/app/services/auth/AGENTS.md` dépassent mesurablement le patron déjà
en place — taille (~2,5× le seuil racine) **et** structure (sections `##`
indépendantes, chacune adossée à un numéro de ticket, sans dépendance entre
elles). `cli/AGENTS.md` et `models/AGENTS.md` sont plus longs que la racine
mais couvrent un sujet unique et cohérent : les fragmenter reviendrait à
disperser un seul raisonnement, pas à retirer un coût de lecture non
pertinent.

## Audit de taille — `docs/*.md` et `.claude/agents/*.md`

Ces fichiers sont **déjà** hors du mécanisme de chargement automatique : ils
se lisent sur renvoi (`AGENTS.md` § « Où lire quoi »), jamais au passage d'une
lecture de fichier voisin. Le coût token n'existe que si l'agent les ouvre —
et seulement pour la tâche qui les cite.

- `docs/WORKFLOW-IA.md` (365 lignes), `docs/ci-cd.md` (529 lignes) : grands
  mais déjà fragmentés en sections `##`/`###` nombreuses et named (18 pour
  `ci-cd.md`) ; un agent qui vient y chercher un point précis peut lire une
  section, pas le fichier entier. Aucune redondance trouvée avec un autre
  fichier. **Inchangés.**
- `.claude/agents/ui-ux-review.md` (201 lignes) : prompt d'un sous-agent
  spécialisé, chargé seulement sur déclenchement explicite de la revue
  UI/UX — au même ordre de grandeur que le plafond que la racine s'impose à
  elle-même. **Inchangé.**

**Conclusion** : aucun fichier `docs/*.md` ou `.claude/agents/*.md` ne remplit
le critère « coût token mesurable » — ils sont déjà dans le régime « sur
renvoi » que le système existant leur réserve. Le split porté par cette
feature se limite donc aux deux `AGENTS.md` de dossier identifiés ci-dessus.

## Volet 4 — commentaires de code : déjà couvert

`.specify/memory/constitution.md`, Principe VI (Simplicité et YAGNI), l. 264-271 :

> Le code par défaut n'a **pas** de commentaires — un identifiant bien nommé
> remplace un commentaire tautologique. Un commentaire n'est justifié que par
> un « pourquoi » non-évident : contrainte cachée, invariant subtil,
> contournement d'un bug tiers.

C'est exactement la règle demandée par l'issue. **Décision : aucun ajout dans
`AGENTS.md`** — dupliquer reviendrait à violer ce même principe (une seule
définition, pas deux formulations à maintenir en cohérence). `AGENTS.md`
renvoie déjà à la constitution pour le Principe I (langue) ; le même renvoi
implicite vaut pour le Principe VI via la section « Principes de conception ».

## Volets 2 et 3 — rédaction

Décision : ajouts courts dans `AGENTS.md` § Conventions générales, sur le
patron déjà en place pour la ligne « Lier une PR à son issue... » (un tiret,
2-4 lignes, pas de nouvelle sous-section). Le volet 2 (assignation GitHub) est
une convention de comportement d'agent, pas un mécanisme — aucune GitHub
Action à créer. Le volet 3 (titres d'issues en anglais) s'ajoute à la clause
existante de la règle de langue (Principe I), qui couvre déjà « titres et
corps de PR à visée technique » mais pas explicitement les issues.

## Contenu déplacé — table de correspondance

### `backend/app/api/AGENTS.md` → `docs/api/`

| Section d'origine (ticket) | Nouveau fichier |
|---|---|
| Sources d'une épreuve (#284), Basculer la source active (#285), Re-scraper à la demande (#118), Aperçu d'impact avant fusion (#286), Fusionner (#287) | `docs/api/courses-sources-fusion.md` (epic #275) |
| Révocation d'urgence des sessions (#169, endpoint), Administration des données (#117), Doublons suspects (#288) | `docs/api/admin-donnees.md` |
| Retours utilisateurs (#267), Statistiques détaillées d'une participation (#272) | `docs/api/feedback-stats.md` |

Restent dans `AGENTS.md` (foundational, appliqué à toute la surface API) :
Portée club et disciplines, Classement d'une épreuve paginé (#163), Protéger
une ressource (#115).

### `backend/app/services/auth/AGENTS.md` → `docs/auth/`

| Section d'origine (ticket) | Nouveau fichier |
|---|---|
| Liste d'autorisation en base (#170) | `docs/auth/liste-autorisation.md` |
| Groupes d'appartenance (#197) | `docs/auth/groupes.md` |

Restent dans `AGENTS.md` (foundational) : Authentification socle SSO (#114),
Autorisation RBAC (#115).
