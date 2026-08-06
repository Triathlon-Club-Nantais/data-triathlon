# Phase 0 — Recherche : lancer les batches depuis l'interface d'administration

**Feature** : `20260806-143754-ops-batch-runs` · **Issue** : #47

Quinze décisions. Les cinq premières fixent l'ossature, les suivantes règlent
des pièges mesurables — deux d'entre eux (D3, D12) sont des impasses connues qui
coûteraient une demi-journée chacune si on les découvrait à l'exécution. La
dernière (D15) répond à la question qui se repose d'elle-même : pourquoi ne pas
streamer, puisque le dépôt sait déjà le faire.

---

## D1 — Plateforme d'exécution : GitHub Actions

**Décision** : un workflow `.github/workflows/batch.yml`, déclenché par
`workflow_dispatch` (à la demande) et `schedule` (périodique), qui lance la CLI
existante sur un runner.

**Rationale** : coût nul sur dépôt public ; le scraping et la connexion à la base
partent du runner, donc le service web gratuit de Render continue de ne servir
que le site (FR-013) ; le journal, la conservation des bilans et la notification
d'échec sont natifs ; la CLI tourne **inchangée**, contrats de sortie compris
(Principe IV).

**Alternatives rejetées** :

| Alternative | Motif |
| --- | --- |
| Render Cron Job | ~1 $/mois minimum, hors offre gratuite ; et nos services étant créés hors Blueprint, `render.yaml` ne le créerait pas (#162). |
| Exécution dans le service web (tâche de fond ou flux SSE) | Contention sur `plan: free` (0,1 CPU), et surtout : un batch lié à une connexion ou à un process ne survit ni à la fermeture de l'onglet, ni à un redémarrage de l'instance, et ne donne ni planification ni alerte. Détail en **D15** — cette piste mérite plus qu'une ligne, le dépôt sachant déjà streamer un import. |
| Cron du serveur Azure du club | Suppose d'y déployer le code et la `DATABASE_URL` : recrée la dépendance à une machine et à une personne, c'est-à-dire le problème d'origine. |

---

## D2 — Transport de la liste d'URL : entrée de `workflow_dispatch`

**Décision** : les URL extraites du fichier sont passées au workflow dans une
**entrée texte**, une URL par ligne. Plafond **500 URL par lot**, refus explicite
au-delà (FR-012).

**Rationale** : aucune table, aucune migration, aucun état à réconcilier. La
documentation GitHub borne `inputs` à **25 propriétés de premier niveau** ; elle
ne documente pas de taille maximale, ce qui est précisément la raison de poser la
nôtre plutôt que de découvrir la leur en production. 500 URL de ~80 caractères
font ~40 Ko.

**Alternative rejetée** : persister le lot en base et ne passer que son
identifiant au runner (qui a déjà la `DATABASE_URL`). C'est le repli si le
plafond devient gênant — noté dans #47 — mais aujourd'hui ce serait une table et
une migration pour un besoin qui ne s'est pas présenté (Principe VI).

---

## D3 — Injection de commande dans le workflow : interdite par construction

**Décision** : **aucune** entrée n'est interpolée dans un `run:`. Chaque valeur
passe par un bloc `env:`, et le script ne lit que des variables shell citées :

```yaml
- env:
    URLS: ${{ inputs.urls }}
  run: printf '%s\n' "$URLS" | uv run python -m app.cli rescrape-db --urls-from -
```

**Rationale** : `${{ inputs.urls }}` écrit directement dans un `run:` est
substitué **avant** l'exécution du shell. Une valeur contenant `"; curl … | sh #`
s'exécute alors avec le jeton du workflow et l'accès à la base de production.
C'est le piège documenté de GitHub sur les entrées de workflow, et il est ici
d'autant plus réel que la valeur vient d'un fichier téléversé par un humain.

**Conséquence** : cette règle est un critère de relecture, pas un détail de
style — toute tâche qui ajoute une entrée au workflow doit la respecter.

---

## D4 — Authentification vers l'API GitHub : jeton fine-grained

**Décision** : un *fine-grained personal access token*, restreint au seul dépôt
`Triathlon-Club-Nantais/data-triathlon`, portant la permission **`actions: write`**
(nécessaire et suffisante pour `POST …/dispatches` et la lecture des exécutions).
Stocké en variable d'environnement Render `GITHUB_BATCH_TOKEN`, absent du dépôt.

**Rationale** : le plus petit pouvoir qui fasse le travail. Une GitHub App
donnerait une rotation automatique et un pouvoir plus fin encore, au prix d'une
installation, d'un JWT signé et d'un échange de jeton d'installation — de la
mécanique pour un seul appelant (Principe VI).

**Coût connu, à documenter** : un jeton fine-grained **expire** (un an au
maximum). Son expiration se manifestera par un 401 sur le lancement : le message
d'erreur doit le nommer, et `docs/ci-cd.md` doit dire où le régénérer.

**Absence de jeton = fonctionnalité indisponible, jamais démarrage en échec** —
même politique que les huit réglages `AUTH_*` (#114) : l'écran annonce que le
lancement n'est pas configuré, le reste de l'application est intact.

---

## D5 — Concurrence : deux gardes, à deux niveaux

**Décision** :

1. dans le workflow, `concurrency: { group: batch-<cible>, cancel-in-progress:
   false }` — c'est le **verrou réel**, il tient même pour un lancement fait
   depuis l'onglet Actions ou par la planification. Le groupe porte la cible :
   preview et production sont deux bases, et faire attendre l'une pendant que
   l'autre travaille n'aurait aucun sens ;
2. dans l'API, refus **409** si une exécution `queued` ou `in_progress` existe —
   c'est ce qui donne à l'utilisateur un message immédiat (FR-004) au lieu d'un
   run qui reste en attente sans explication.

**Rationale** : la garde d'interface seule serait contournable ; la garde de
plateforme seule serait muette. Aucune des deux ne remplace l'autre.

---

## D6 — Lecture du bilan : artefact JSON, lu à la demande

**Décision** : le workflow écrit deux sorties — le rapport texte dans
`$GITHUB_STEP_SUMMARY` (lisible sur la page du run) et la charge `--json` dans un
**artefact** `bilan-<id>.json`. L'API télécharge l'artefact (`GET
…/artifacts/{id}/zip`), l'ouvre en mémoire (`zipfile` de la stdlib) et rend le
JSON tel quel.

**Rationale** : FR-015 veut les compteurs **dans l'interface**, pas seulement un
lien vers GitHub. L'artefact est la seule sortie machine-lisible que la
plateforme conserve ; il pèse quelques kilo-octets (le détail est borné aux seuls
échecs, cf. `cli/AGENTS.md`).

**Alternatives rejetées** : parser le log du job (fragile, non contractuel) ;
faire poster le bilan par le workflow à un endpoint dédié (secret partagé
supplémentaire, et une table pour le stocker).

**À ne pas oublier** : `--json` met le rapport texte sur **stderr** et ne laisse
que la ligne JSON sur stdout (Principe IV). Le workflow redirige donc stdout vers
le fichier d'artefact et laisse stderr aller au journal — c'est exactement l'usage
pour lequel ce contrat existe.

---

## D7 — Extraction du fichier : un seul chemin après lecture

**Décision** : `services/sheet_source.py` gagne deux fonctions —
`read_table(content: bytes, filename: str) -> (headers, rows)` qui absorbe
CSV et XLSX, et `links_in_column(rows, index)` qui en tire les liens. Identifiants
en anglais : ce sont des ajouts, donc sous la règle du Principe I, sans exception
de vocabulaire métier. Le
parcours de colonne existant (`parse_sheet_csv`) devient un appelant de ces
deux-là, avec `LINK_HEADER` et l'index 9 conservés comme **défauts de la
commande CLI**.

**Rationale** : le module fait déjà exactement ce travail pour le Google Sheet —
sélection de colonne par en-tête, `normalize_url`, `dedupe_links`, `is_supported`,
`host_of`. Le besoin est de rendre la colonne **paramétrable**, pas d'écrire un
second extracteur. Aucun accès base, aucun état : le module reste conforme au
Principe II.

---

## D8 — Lecture XLSX : `openpyxl`, et ce qu'elle ne verra pas

**Décision** : dépendance `openpyxl`, ouverte en `read_only=True, data_only=True`.
Seules les **valeurs texte** des cellules sont lues.

**Rationale** : bibliothèque établie, sans dépendance lourde, et c'est la seule
brique qui manque (le CSV reste la stdlib). `read_only` évite de charger le
classeur entier en mémoire.

**Deux limites assumées, à dire à l'utilisateur plutôt qu'à contourner** :

- un lien posé en **hyperlien de cellule** sans texte visible n'est pas lu
  (`read_only` ne charge pas les hyperliens) ;
- un lien produit par une **formule** (`=HYPERLINK(…)`) n'est lu que si le
  classeur porte la valeur calculée en cache.

Dans les deux cas la colonne affichera « 0 lien détecté », ce qui est un
diagnostic lisible — et non un import silencieusement vide. C'est ce qui fait de
FR-007 (le compte de liens par colonne) une exigence de sûreté autant que de
confort.

---

## D9 — Le fichier téléversé ne touche pas le disque durablement

**Décision** : la taille est comptée **en lisant par morceaux**, pas d'après
`Content-Length` ; au-delà de 2 Mo la lecture s'arrête et la requête est refusée.
Aucune écriture applicative sur disque, aucun répertoire temporaire à nettoyer.

**Rationale** : `Content-Length` est déclaratif — s'y fier laisserait entrer un
corps plus gros que ce qu'il annonce. Starlette expose le corps par un
`SpooledTemporaryFile` qui bascule sur un fichier temporaire **anonyme** au-delà
d'un mégaoctet ; ce fichier est détruit à la fermeture de la requête, ce qui
satisfait FR-011 (« au-delà de la requête qui le traite »). Le point mérite d'être
écrit parce qu'il se vérifie mal après coup.

---

## D10 — Deux pouvoirs, ajoutés au catalogue

**Décision** : `P.BATCH_RUN` (`batch:run`, « Lancer un batch ») et `P.BATCH_READ`
(`batch:read`, « Consulter les batches »), sous une fonctionnalité
`FEATURE_BATCH = "Batches"`.

**Rationale** : ajouter un membre à `P` ne demande **aucune migration** — c'est la
propriété centrale du modèle de #115. Le geste nomme l'acte métier, pas un CRUD.

**Contrainte de séquencement** : le méta-test AST du catalogue
(`tests/test_permissions_catalogue.py`) exige qu'aucun pouvoir ne garde zéro
ressource. Les deux pouvoirs et leurs routes doivent donc arriver **dans la même
tâche** ; les déclarer d'abord et poser les gardes ensuite laisse la suite rouge
entre les deux.

---

## D11 — Catalogue fermé des lancements

**Décision** : le corps accepté par l'API est une union discriminée Pydantic —
`mode: Literal["rescrape", "fichier"]` — avec des options **typées et bornées** :
`provider` validé contre le registre des scrapers, `older_than` et `limit` bornés
par des entiers positifs, `dry_run` booléen. Les URL du mode « fichier » sont
normalisées, dédoublonnées, puis filtrées sur `registry.is_supported` avant tout
envoi.

**Rationale** : cet endpoint déclenche l'exécution de code sur un runner qui
détient la base de production. Le seul modèle défendable est une liste blanche de
formes valides, pas un assainissement de chaîne libre (FR-003). C'est la même
raison qui interdit `--provider` inconnu côté CLI, rejeté avant tout travail
(code 2).

---

## D12 — Connexion à Supabase depuis un runner : le piège IPv6

**Risque identifié** : les runners GitHub hébergés **n'ont pas d'IPv6**. L'hôte de
connexion **directe** de Supabase (`db.<ref>.supabase.co`) résout en IPv6 seule
sur les projets récents : une `DATABASE_URL` pointant dessus donnerait un échec de
connexion réseau au premier batch, sans rapport apparent avec le code.

**Mitigation** : le secret `DATABASE_URL` de l'environnement d'exécution doit
viser le **pooler** Supabase (hôte `…pooler.supabase.com`), joignable en IPv4.
À vérifier **avant** la première exécution réelle, et à écrire dans
`docs/ci-cd.md` — c'est le genre de contrainte qu'on ne retrouve pas six mois
plus tard.

**Effet de bord à connaître** : en mode *transaction* le pooler ne supporte pas
les instructions préparées côté serveur ; le mode *session* est le repli sûr pour
un batch qui ouvre une connexion longue.

---

## D13 — Planification : hebdomadaire, et elle s'éteint toute seule

**Décision** : `schedule` hebdomadaire de nuit, cadence à confirmer après la
première mesure de durée réelle.

**Piège documenté** : GitHub **désactive** les workflows planifiés d'un dépôt
resté sans activité pendant 60 jours. Le dépôt est actif, le risque est faible —
mais l'absence silencieuse d'exécution est exactement le genre de panne que
personne ne voit. Le critère SC-007 (quatre échéances consécutives) est ce qui la
révélerait.

---

## D14 — Interface : deux appels, aucun état serveur

**Décision** : l'écran envoie le fichier **deux fois** — une première pour obtenir
les colonnes, une seconde avec la colonne retenue pour lancer. `lib/api/client.ts`
gagne une fonction d'envoi multipart distincte de `request()`.

**Rationale** : c'est ce qui permet FR-011 sans stockage intermédiaire. Le fichier
est borné à 2 Mo, le second envoi est donc sans conséquence perceptible.

**Détail qui casse si on l'oublie** : `request()` pose
`Content-Type: application/json` sur **toutes** les requêtes. Réutilisé tel quel
pour un envoi multipart, il empêcherait le navigateur d'écrire la frontière
(`boundary`) et le serveur ne lirait aucun champ.

---

## D15 — Pourquoi pas un flux SSE, alors que le dépôt en a déjà un

**La question se repose naturellement**, et c'est pour cela qu'elle est écrite
ici : `POST /scrape/event/stream` fait déjà exactement ce geste — import d'une
épreuve, progression en direct, padding anti-buffering, `Content-Encoding:
identity` pour survivre aux intermédiaires. Mieux : `iter_import_event` est
consommé **à la fois** par ce SSE et par `services/batch.py`. Un
`POST /admin/batches/stream` tiendrait en une trentaine de lignes, sans jeton,
sans seconde plateforme, sans artefact à dézipper.

**Décision : non — mais l'argument de la contention seule ne suffit pas.**

Rectification d'abord, parce qu'elle a été énoncée trop fort ailleurs : un batch
dans le service web ne « monopolise » pas l'instance. Les handlers sont `def` et
non `async def`, donc FastAPI les exécute dans un threadpool ; le site continue
d'être servi pendant le scraping. Le coût réel est une **dégradation** sur 0,1
CPU, pas un blocage. Une justification fausse est une justification qui tombera.

Ce qui tranche, ce sont quatre propriétés qu'un flux ne peut pas porter :

1. **Le suivi vit dans la connexion.** Fermer l'onglet, c'est perdre le batch de
   vue. Or la spec porte l'edge case inverse — « le traitement se poursuit, son
   bilan reste consultable au retour ». Le rendre vrai demanderait de persister
   l'état : exactement la table qu'on a évitée (Principe VI).
2. **Un redémarrage de l'instance tue l'exécution en cours.** Déploiement,
   rotation d'instance sur l'offre gratuite, OOM. Les épreuves déjà commitées
   restent — chacune l'est séparément — mais plus personne ne sait où le batch
   s'est arrêté.
3. **FR-018 exige un ordonnanceur de toute façon.** Avec le SSE, il faudrait
   *en plus* un cron externe appelant l'API : deux mécanismes au lieu d'un, et
   celui qui planifie n'aurait aucun suivi.
4. **Ni trace ni alerte** — soit les deux griefs qui ouvrent #47. Il faudrait
   les construire, là où la plateforme d'exécution les donne.

**Inconnue non levée** : le comportement du proxy Vercel sur un flux de 25
minutes. Le SSE actuel tient ~35 s en usage réel ; rien ne dit qu'un rewrite
externe reste ouvert à l'échelle d'un batch complet. Ne pas partir du principe
que oui.

**Le repli, si le bilan-à-la-fin se révèle insuffisant** : faire pousser la
progression par le workflow vers un endpoint de l'API, qui la relaie en SSE à
l'écran. On obtient alors le direct **et** la durabilité, sans que le service web
porte le travail. Coût : un endpoint authentifié et un état à tenir. À faire le
jour où le besoin se manifeste, pas d'avance.

## Ce que la recherche laisse ouvert

- **Le comportement réel des chronométreurs depuis une IP de centre de données**
  ne se sait qu'en essayant (noté dans #47). Le premier lancement doit être une
  simulation bornée, puis un lot réel de quelques épreuves.
- **La cadence de la planification** dépend de la durée mesurée d'une reprise
  complète.
