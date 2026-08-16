# Compteurs de rang du dashboard calculés côté backend — design

**Issue** : [#376](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/376)
**Date** : 2026-08-16
**Statut** : design validé, à implémenter

## Le problème

Un commentaire du 2026-08-16 sur #376 constate, en inspectant le payload RSC de
`/dashboard`, que **toutes les participations du club** (jusqu'à 5000 lignes,
`page_size=5000`) sont embarquées telles quelles dans le HTML envoyé au
navigateur.

Cause : `StatCardsRank` (`frontend/components/dashboard/StatCardsRank.tsx`)
reçoit le tableau `participations` **en entier** pour recalculer localement,
via `rankCounters` (`frontend/lib/utils/club-aggregate.ts`), les compteurs
Victoires / Podiums / Top 10 selon le mode de rang sélectionné (`?rank=` —
`scratch` / `category` / `gender` / `all`). Ce choix est volontaire (#132,
#328) : `RankTypeToggle` écrit l'URL en `pushState`, pas en `router.push`, pour
que le changement de mode ne redéclenche ni fetch ni re-rendu serveur.

Le problème n'est donc pas ce choix (le toggle doit rester instantané et sans
réseau), mais son coût : sur `/dashboard`, `participations` n'alimente **que**
`StatCardsRank` — `dashboard/page.tsx` ne le passe à rien d'autre — pour
produire in fine 3×4 entiers. Envoyer 5000 objets `Participation` complets
pour ce résultat est disproportionné, et c'est ce volume, combiné à l'absence
de cache HTTP déjà en partie traitée par #352, qui domine le temps de réponse
mesuré dans le sondage du 2026-08-15
(`docs/superpowers/specs/2026-08-15-perf-frontend-remesure-352.md`).

Deux points annexes de #376 :

- `/ajouter` (`apiServer.listEvents(...)`) est prefetché par le bouton « + »
  de la navigation globale (`AppNav`, monté sur **toutes** les pages), sans
  aucune fenêtre de `revalidate` — chaque survol/prefetch déclenche un appel
  backend live.
- Le favicon et un possible « fetch sans réponse » signalés dans le corps
  initial de l'issue restent hors de ce design (voir « Hors périmètre »).

## Décisions de cadrage

| Question | Décision |
| --- | --- |
| Où calculer les compteurs | **Backend**, dans `stats_service.get_stats` — réutilise la liste `parts` déjà chargée pour `by_type`/`by_month`/`recent`, zéro requête SQL supplémentaire |
| Nouvelle route ? | **Non** — nouveau champ `rank_counters` dans la réponse existante de `GET /stats`, déjà appelée par `/dashboard` |
| Le toggle `?rank=` doit-il re-fetcher ? | **Non**, invariant de #132/#328 : les 4 modes sont calculés d'un coup côté backend, le client choisit celui à afficher sans réseau |
| `apiServer.listParticipations` sur `/dashboard` | **Supprimé** — plus aucun consommateur sur cette page une fois `StatCardsRank` migré |
| `/club` | **Hors périmètre**, audité et écarté (voir plus bas) |
| `/ajouter` | `listEvents()` reçoit la même fenêtre `SHORT_REVALIDATE_SECONDS` que #352, sur le même patron |

### Pourquoi `/club` n'a pas le même problème

`/club` (`app/club/page.tsx`) charge aussi `participations` (jusqu'à 1000
lignes), mais `ClubDashboard` les distribue à plusieurs consommateurs qui ont
réellement besoin des lignes individuelles à l'affichage : `buildRoster`
(fiche par athlète), `PodiumsList` et `recentParticipations` (cartes de
résultat avec athlète/épreuve/date), en plus de `ClubPodiumKpi` (le même genre
de compteur que `StatCardsRank`, mais qui n'est pas le seul consommateur).
Retirer le tableau brut de la page casserait le roster et les listes — la
page a besoin des objets complets de toute façon. Rien à changer ici.

### Forme de `rank_counters`

Un objet couvrant les 4 modes en une passe sur `parts`, miroir de
`RankCountersResult` côté front (`frontend/lib/rank.ts`,
`frontend/lib/utils/club-aggregate.ts`) :

```json
{
  "scratch": {"victories": 12, "podiums": 34, "top10": 88},
  "category": {"victories": 9,  "podiums": 28, "top10": 71},
  "all":      {"victories": 14, "podiums": 39, "top10": 92},
  "gender": {
    "women": {"victories": 3, "podiums": 11, "top10": 30},
    "men":   {"victories": 9, "podiums": 23, "top10": 58}
  }
}
```

`StatCardsRank` n'a alors plus besoin de `Participation[]` en prop : il lit
`rank_counters[rankType]` (ou `rank_counters.gender` en mode genre) selon
`?rank=`, exactement comme aujourd'hui avec `rankCounters(participations,
rankType)` — seul le calcul change de côté, le comportement au clic reste
identique.

### Pourquoi étendre le revalidate à `/ajouter`

Le sondage du 08-15 avait délibérément exclu `/ajouter` et `/resultats` de la
fenêtre courte de #352 : leur `listEvents()` n'a pas de filtre
`scope=club`/`seasons`, donc pas le même profil de coût mesuré à l'époque.
`/ajouter` reste néanmoins prefetché en continu par un lien présent sur
**toutes** les pages (bouton « + » de `AppNav`), ce qui en fait un appel
backend récurrent et non nécessaire à chaque navigation — c'est ce prefetch,
pas le coût par appel, qui justifie ici la fenêtre courte. `/resultats` n'est
pas concerné (pas de prefetch global équivalent) et reste inchangé.

## Ce qui ne change pas

- Le comportement au clic sur `RankTypeToggle` (pushState, zéro réseau).
- `/club` et ses composants.
- La structure de `GET /stats` pour les consommateurs existants — `rank_counters`
  est un champ **ajouté**, aucun champ retiré ni renommé (Principe IV).

## Hors périmètre

- **Le « fetch sans réponse »** signalé dans le corps initial de l'issue —
  l'hypothèse la plus probable (payload disproportionné, non caché) est
  traitée par ce design ; à ré-instruire seulement si le symptôme persiste
  une fois ce correctif en préview.
- **Le favicon** — aucune configuration de cache anormale trouvée, pas de
  piste de code à ce stade.
- **La combinaison lente `scope=club` + `seasons=...` sur `courses/events` et
  `participations`**, identifiée comme un « tiers défaut » par le sondage du
  2026-08-15 (857-971 ms, indépendant du volume ou du cache) : explicitement
  notée dans ce sondage comme hors périmètre de #352 et à ouvrir séparément —
  ce design ne la traite pas non plus.
- **#414** (Vercel Middleware / Proxy) — clos séparément, sans rapport avec ce
  design (voir commentaire de clôture sur l'issue).

## Tests

TDD (Principe III) des deux côtés :

- Backend : `tests/test_services/test_stats_service.py` (ou fichier
  équivalent) — cas par mode (`scratch`/`category`/`all`/`gender`), y compris
  l'emboîtement victoires ≤ podiums ≤ top10 et la ventilation F/H déjà
  couverte côté front par `club-aggregate.test.ts`, à répliquer côté Python
  puisque la logique change de couche.
- Frontend : `StatCardsRank.test.tsx` migre vers une prop `rankCounters`
  (fixture) au lieu de `participations` ; `dashboard/page.test.tsx` vérifie
  la disparition de l'appel `listParticipations` et le passage du nouveau
  champ à `StatCardsRank`.
