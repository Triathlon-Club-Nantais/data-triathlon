# Validation de bout en bout

Douze vérifications, dans l'ordre où elles cessent d'être bloquantes les unes
pour les autres. Les six premières sont locales et sans réseau ; les six
dernières demandent le dépôt réel.

**Le point de bascule est la §7, et il conditionne la livraison.** Un
`workflow_dispatch` n'est déclenchable que si le fichier de workflow se trouve
sur la branche par défaut : la §7 n'est donc exécutable **qu'après le merge de la
PR 1** (le workflow seul, cf. `plan.md` §Livraison). Les §8 et suivantes
supposent en plus la PR 2 mergée. Ce n'est pas un ordre de confort — c'est ce que
la plateforme impose, et c'est aussi ce qui fait découvrir le piège de connexion
(D12) avant qu'on ait construit dessus.

## Prérequis

```bash
cd backend && uv sync                 # openpyxl inclus
cd frontend && npm ci
```

Pour les §7 et suivantes : un jeton fine-grained (`actions: write`, dépôt seul)
dans `backend/.env` sous `GITHUB_BATCH_TOKEN`, et l'environment GitHub
`batch-production` portant `DATABASE_URL`.

---

## 1. Extraction d'un fichier — sans réseau

```bash
cd backend && uv run pytest tests/test_services/test_sheet_source_upload.py -q
```

Attendu : lecture d'un `.csv` **et** d'un `.xlsx` (le classeur est fabriqué en
mémoire dans le test, aucun binaire versionné), comptage des liens par colonne,
en-tête manquant remplacé par « Colonne N », dédoublonnage, et partage entre
liens supportés et `ignored_by_host`.

## 2. Gardes de frontière — sans réseau

```bash
uv run pytest tests/test_api/test_admin_batches.py -q
```

Attendu, un test par refus : extension inconnue (422), > 2 Mo (413), colonne hors
bornes (422), colonne sans lien (422), > 500 URL (422), batch déjà en cours
(409), jeton absent (503), sans session (401), sans pouvoir (403).

Vérifier en lisant les tests, pas seulement leur couleur : **aucun** ne doit
sortir sur le réseau, l'API GitHub étant jointe par `MockTransport`.

## 3. Le catalogue de pouvoirs reste cohérent

```bash
uv run pytest tests/test_permissions_catalogue.py -q
```

Attendu : `batch:run` et `batch:read` sont dans `ALL`, et chacun garde au moins
une route. Ce test rougit si les pouvoirs sont déclarés sans que les gardes
suivent (D10).

## 4. Le workflow ne peut pas être détourné

Relecture, pas de commande : dans `.github/workflows/batch.yml`, **aucune**
occurrence de `${{ inputs.` à l'intérieur d'un bloc `run:`.

```bash
grep -n 'run:' -A 5 .github/workflows/batch.yml | grep 'inputs\.'   # doit ne rien rendre
```

Une correspondance ici est une injection de commande sur un runner qui détient la
base de production (D3).

## 5. La CLI reste intacte

```bash
cd backend && uv run pytest tests/test_cli -q
uv run python -m app.cli rescrape-db --limit 1 --dry-run --json | jq -e '.unique_supported? // .epreuves? // 0'
```

Attendu : stdout ne porte que du JSON, le rapport texte est allé sur stderr,
code de sortie 0. Cette feature **dépend** de ce contrat, elle ne le modifie pas.

## 6. L'écran, sans backend

```bash
cd frontend && npm test && npm run build
```

Attendu : téléversement d'un fichier → colonnes listées avec leur compte de
liens, colonne présélectionnée, lancement désactivé tant qu'aucune colonne n'est
retenue, message de refus affiché tel que rendu par l'API (jamais réécrit côté
interface).

---

## 7. La base est joignable depuis un runner — **après merge de la PR 1, avant tout batch réel**

Depuis l'onglet Actions, lancer `batch.yml` en `mode: rescrape`, `limit: 1`,
`dry_run: true`.

Attendu : exécution verte en moins d'une minute.

En cas d'échec de connexion, c'est presque certainement D12 : la `DATABASE_URL`
de l'environment vise l'hôte direct de Supabase, résolu en IPv6 seule, alors que
les runners GitHub n'ont pas d'IPv6. Basculer sur l'hôte du **pooler**, puis
recommencer. Ne pas passer à la §8 avant que celle-ci soit verte.

## 8. Un lancement depuis l'interface aboutit

Depuis `/admin/batches`, avec un compte porteur de `batch:run` : reprise filtrée,
`limit: 5`, simulation cochée.

Attendu : l'écran passe en « en attente » puis « en cours », l'exécution apparaît
dans la liste avec le bon libellé, et le bilan s'affiche à la fin — compteurs en
épreuves et en participants nommés comme tels.

## 9. Le second lancement est refusé

Pendant que la §8 tourne, relancer.

Attendu : refus immédiat avec un message qui nomme l'exécution en cours (409), et
**aucune** seconde exécution sur la page des Actions.

## 10. Un vrai import de fichier

Téléverser un fichier réel du club (`.xlsx`), désigner la colonne de liens,
lancer **sans** simulation, borné à quelques épreuves.

Attendu : les épreuves apparaissent en base et le bilan liste les liens non
supportés à part.

Sur la non-persistance du fichier (FR-011), la preuve est **le test**, pas
l'inspection : la plateforme n'offre pas de shell, et « je n'ai rien vu » n'est
pas une vérification. Le test de §2 assure qu'aucune écriture applicative n'a
lieu dans ce chemin (SC-005) ; le tampon temporaire de la couche HTTP, lui, est
anonyme et détruit à la fermeture de la requête (D9).

C'est ici que se mesure le comportement des chronométreurs depuis une IP de
centre de données (risque ouvert de `research.md`). Un échec massif et uniforme
sur un seul fournisseur, alors que la même URL passe depuis un poste, est le
symptôme à reconnaître.

## 11. Le site public ne ralentit pas pendant un batch

Pendant que le batch de la §10 tourne, relever deux fois le temps de réponse
d'une page publique, puis le comparer au relevé de repos :

```bash
for i in 1 2 3; do curl -s -o /dev/null -w '%{time_total}\n' https://<domaine>/api/v1/health; done
```

Attendu : aucun écart perceptible entre les deux relevés (SC-004). C'est la
vérification qui **justifie l'architecture retenue** — si le batch tournait dans
le service web, l'écart serait immédiat. Deux mesures suffisent : l'enjeu n'est
pas la précision, c'est de constater qu'il ne se passe rien.

## 12. L'alerte fonctionne

Lancer une reprise ciblant une épreuve dont la source est certainement en échec
(URL d'un fournisseur supporté mais page retirée).

Attendu : l'exécution est **rouge** (échec total, code 1) et la notification part.
Puis vérifier l'inverse : une reprise dont une seule épreuve sur cinq échoue
reste **verte**, avec le détail de l'épreuve fautive dans le bilan. C'est SC-003,
et c'est la seule vérification qui distingue une alerte utile d'une alerte qui
crie tout le temps.

**Et vérifier qui l'a reçue.** Une alerte partie vers personne ne vaut rien : la
plateforme notifie par défaut l'auteur de la dernière modification de la
planification, pas l'équipe. Constater le destinataire réel, le noter dans
`docs/ci-cd.md`, et si ce n'est pas la bonne personne, rouvrir l'hypothèse de la
spec (« aucun canal d'alerte nouveau ») plutôt que de vivre avec.
