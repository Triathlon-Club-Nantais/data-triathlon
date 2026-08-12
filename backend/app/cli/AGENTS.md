# Sorties de la CLI (stdout parsable)

## Les invocations, depuis `backend/`

```bash
uv run python -m app.cli import-sheet --dry-run     # import de masse (Sheet) : ce qui serait importé
uv run python -m app.cli import-sheet --limit 5     # import réel — progression en direct
uv run python -m app.cli rescrape-db --limit 10     # re-scrape la DB (force=True) ; --plain, --no-progress
uv run python -m app.cli rescrape-db --json | jq    # bilan machine-lisible (stdout = JSON seul)
uv run python -m app.cli rescrape-db --url <url> --url <url2>   # cible des épreuves précises
uv run python -m app.cli rescrape-db --urls-from echecs.txt     # ou « - » pour lire stdin
# rejeu des échecs, sans fichier intermédiaire ni état persistant :
uv run python -m app.cli import-sheet --json | jq -r '.failures[].url' \
  | uv run python -m app.cli rescrape-db --urls-from -
uv run python -m app.cli club-labels --like nant   # libellés club vus en base, marqués TCN ou non
uv run python -m app.cli allow-email --email <adresse>              # autorise une adresse à se connecter (#170)
uv run python -m app.cli grant-role --email <adresse> --role admin   # amorce le 1er administrateur (#115)
uv run python -m app.cli revoke-sessions --all --yes                 # révocation d'urgence : ferme toutes les sessions (#169)
uv run python -m app.cli revoke-sessions --email <adresse>           # ou celles d'une adresse seulement
```

Les trois dernières sont les commandes d'**amorçage**, décrites une par une plus
bas ; l'ordre qui marche sur une base neuve est `allow-email` → connexion par le
navigateur → `grant-role`.

## La couche

`app/cli/` est une **couche mince**, zéro logique métier : `commands/` (une
commande par fichier), `progress.py` (reporters Rich/Plain, `select_reporter`),
`reports.py` (rendu des bilans + émission). La boucle vit dans
`services/batch.py` — elle consomme `import_service.iter_import_event()`, le
générateur de phases du SSE, et relaie la progression via le Protocol
`ProgressReporter` de `services/progress.py` (`NullReporter` = le défaut muet).

Règle structurante, pas un détail : **stdout reste parsable**. La progression sort
donc toujours sur **stderr** (Rich en terminal, lignes simples sinon — cron, CI,
redirection), et avec `--json`, le rapport texte y bascule aussi : stdout ne
contient alors **que** la ligne JSON, d'où `… --json | jq` sans découpage. Sans
`--json`, le rapport texte sort sur stdout comme attendu.

Un batch interrompu (Ctrl-C) émet son **bilan partiel** — texte et, le cas
échéant, JSON — **avant** de sortir en code **130** : le travail déjà persisté
n'est jamais perdu de vue (chaque épreuve est commitée séparément). `--no-progress`
coupe la progression (le rapport final, lui, est toujours émis) ; `--plain` force
les lignes simples même en terminal.

**Codes de sortie** (`cli/reports.emit_outcome`) — le bilan est **toujours émis
avant** la sortie :

| Code | Sens |
| --- | --- |
| `0` | Succès, y compris **partiel** (quelques épreuves en échec sur N) ou « rien à faire » (zéro épreuve ciblée). Un dry-run sort toujours en 0. |
| `1` | **Échec total** : aucune des épreuves ciblées n'a abouti (`batch.est_echec_total` : `errors >= épreuves > 0`). Sinon un cron dont les 53 épreuves échouent n'alerterait jamais. |
| `2` | **Erreur d'usage** (convention Click) : option invalide — notamment `--provider` / `--only-provider` inconnu, rejeté avant tout travail par `cli/validators`, ou `--url` désignant une **source passive** (#282, voir plus bas). |
| `130` | Ctrl-C. **Prioritaire sur 1** : une interruption est une action de l'opérateur, pas une panne. |

Un tube fermé (`… | head -2`) ne fausse aucun de ces codes : le `BrokenPipeError`
est rattrapé, et le bilan bascule sur stderr plutôt que d'être perdu.

**Où ces batches tournent désormais** (#47) : plus sur un poste de développement,
mais sur un runner GitHub Actions (`.github/workflows/batch.yml`), déclenché
depuis `/admin/batches` ou par une planification hebdomadaire. Rien n'a changé
dans la CLI — c'est bien elle qui s'exécute — mais le workflow **dépend** de deux
propriétés décrites ci-dessus, et les casser casserait l'écran d'administration
sans qu'aucun test de la CLI ne bouge :

- **la séparation stdout/stderr** : avec `--json`, stdout est redirigé vers
  l'artefact du bilan et stderr vers le rapport. Capturer les deux ensemble
  rendrait l'artefact invalide, et le bilan illisible par `GET …/report` ;
- **le code de sortie** : c'est lui qui rend l'exécution rouge ou verte, donc
  lui seul qui alerte. Le `1` d'échec total est la seule alerte du dispositif —
  il n'y a **aucun** autre canal.

Le workflow n'invente aucune option : il compose la même ligne de commande que
celle documentée ici, à partir d'un catalogue fermé d'entrées.

**Vocabulaire** : la CLI compte des **épreuves** (une source **active** unique),
jamais des courses. Une épreuve porte N `Course` en base (heats Breizh Chrono,
variantes individuel/relais) : `rescrape-db` dédoublonne par URL de source active
avant le batch, donc « Épreuves ciblées : 12 » sur une table de 53 courses n'est
pas une perte.

**Deux modes de sélection pour `rescrape-db`**, exclusifs l'un de l'autre :
par filtre sur la base (`--provider`, `--older-than`), ou par URL explicite
(`--url`, répétable, et `--urls-from <fichier|->`). Le second **court-circuite
la base** : une URL inconnue en table `course` est scrapée normalement, sans
avertissement — c'est le cas nominal du rejeu d'un échec d'import, dont
l'épreuve n'a rien persisté. Les combiner est une erreur d'usage (code 2) : ce
sont deux modes, pas des filtres à composer. `--limit` reste compatible avec les
deux : il borne la liste finale, il ne sélectionne rien.

**Ce que le rescrape ne touche jamais : les sources passives** (#282). Une épreuve
publiée par deux chronométreurs porte N sources dont une seule active, et le batch
ne scrape que celle-là — `--provider` nomme donc le provider de l'**active**, et
une épreuve sans source active (saisie manuelle, ou passives seules) n'est pas
ciblée du tout. Sans ce filtre, `rescrape-db` recréait les doublons que la table
des sources existe pour supprimer.

Corollaire côté ciblage explicite, seule exception au « URL inconnue = scrapée
sans avertissement » : une URL **connue mais passive** est **refusée**, en nommant
l'épreuve et sa source active, en **code 2** et sur **stderr** (stdout reste le
canal `--json`). Le refus est **global** — aucune URL du lot n'est scrapée : un
bilan partiel doublé d'un code 2 ne se lirait ni comme un succès ni comme un
refus. Ce `2` s'appuie sur le même précédent que `revoke-sessions --email
<inconnue>` : une erreur d'usage se constate parfois en base, et « rejeté avant
tout travail » veut dire avant le premier scrape, pas avant la Session.

**Deux unités dans un bilan**, et chaque libellé doit le dire : « Épreuves
ciblées / traitées / en erreur » comptent des **épreuves** ; « Participants
ajoutés / mis à jour / déjà en base » comptent des **participants** (ce
troisième compteur distingue l'upsert d'un simple `skipped` : une
participation déjà en base dont un champ a changé est mise à jour, pas
seulement conservée). Ne pas revenir à des libellés muets sur l'unité
(« Importées / Ignorées ») : lus sous « Épreuves ciblées : 42 », ils se
comprennent en épreuves, et « Ignorées : 5820 » devient un non-sens.
« Épreuves traitées » n'apparaît que sur un bilan interrompu, où elle situe le
Ctrl-C (7 des 42).

**Détail des épreuves en erreur** : le compteur « Épreuves en erreur : N » dit
*combien*, pas *lesquelles*. **Les deux commandes** listent donc les échecs
(URL + cause) sous « Épreuves en erreur (détail) : » — la boucle `batch`
collecte un `BatchFailure(url, label, message)` par épreuve fautive (phase
`error` ou exception rattrapée). Ce détail est aussi dans la charge `--json`
(`failures`), et borné aux seuls échecs : il reste léger, contrairement à la
liste de toutes les épreuves. C'est lui qui referme la boucle de rejeu
(`… --json | jq -r '.failures[].url' | … rescrape-db --urls-from -`), sans
fichier d'état. À distinguer des **liens non supportés** (`ignored_by_host`,
suivis dans #33) : ces derniers ne sont **jamais** soumis au batch, ils ne
comptent ni en succès ni en échec.

**Sources enregistrées, non principales** (#283) — le troisième cas, qui n'est ni
l'un ni l'autre. Une URL soumise pour une épreuve **déjà connue** est rattachée à
elle comme source secondaire : rien n'échoue, rien n'est ajouté au classement, et
les compteurs ne bougent donc pas d'un iota. Les deux commandes listent ces URLs
sous « Sources enregistrées, non principales (détail) : », avec le message qui
**nomme l'épreuve** — sans lui, l'opérateur d'un import Sheet de 300 lignes ne
peut pas distinguer une URL absorbée d'un import ordinaire à zéro nouveauté. Le
champ `passive_sources` est dans la charge `--json`, et dans `CHAMPS_COMMUNS` :
`run_batch` les collecte pour les deux commandes, deux rendus divergeraient sans
raison. À ne pas confondre avec le refus de #282, qui porte sur une URL **déjà**
passive passée à `--url` : celui-là est une erreur d'usage (code 2) et ne scrape
rien ; celui-ci constate après coup, sur une URL que rien ne permettait de
refuser d'avance.

**Réconciliation de l'identité d'athlète** (issue #66) : `rescrape-db` n'est plus
purement additif. Sur un dossard déjà en base, il **résout l'athlète** et, si la
graphie stockée a divergé de la graphie corrigée, **réassigne
`participation.athlete_id`** — puis supprime en fin de batch les fiches d'athlète
ainsi vidées (`athlete_repository.delete_orphans`, no-op sur une base sans
orphelin). Le bilan compte, unités nommées : « Participations réconciliées »,
« Athlètes fusionnés », « Athlètes orphelins supprimés », avec le détail
`ancien -> nouveau (N participations)` — repris dans `--json`.

Il ne réconcilie **que** l'identité : temps, rangs, statuts et splits d'une
participation existante restent intouchés. Ce silence sur les valeurs est
délibéré (idempotence contre additivité : une autre question, une autre issue).
Garde structurante : une correction qui **viderait le prénom** n'est jamais
appliquée (cas « JP ROUX » / prénoms stockés en majuscules).

Le nettoyage des orphelins (`delete_orphans`) ne tourne **que** dans
`rescrape-db`, en fin de batch : le chemin web (`import_event`/SSE, une épreuve
à la fois) réassigne et commite mais **ne** balaie **pas** l'ancienne fiche
vidée — elle reste orpheline jusqu'au prochain `rescrape-db`, qui seul peut
constater qu'aucune autre épreuve du batch ne l'a entre-temps réutilisée.

`--dry-run` a changé de nature : il **scrape désormais** (le prix d'un aperçu
véritable) et **ne persiste rien** (rollback au lieu de commit). Il rend le détail
`avant -> après` sans écrire. `--limit` / `--url` le bornent. Un dry-run sort
toujours en code 0.

## `grant-role` — l'amorçage hors ligne (#115)

```bash
uv run python -m app.cli grant-role --email <adresse> --role admin [--organisation <slug>]
```

Sur une installation neuve, personne ne porte de rôle et les ressources qui les
distribuent en exigent un. C'est la sortie de boucle, et le seul rattrapage si
l'installation se retrouve sans administrateur par un chemin que l'application ne
contrôle pas.

Pas de `--json` : ce n'est pas un batch, il n'y a pas de bilan à piper. Rapport
sur **stdout**, journaux sur stderr, comme le reste. Codes de sortie : `0` pour
l'attribution **et** pour « rien à faire » (relancer par acquit de conscience ne
doit pas ressembler à un échec), `2` pour toute erreur d'usage — adresse
inconnue, adresse **ambiguë**, slug de rôle inconnu, rôle propre à une autre
organisation.

**Elle ne crée ni utilisateur ni rôle.** Un utilisateur naît d'une connexion
réussie et autorisée ; composer un rôle est un geste d'administration qui passe
par l'API. L'adresse ambiguë n'est pas un cas d'école : `users.email` n'est pas
unique, délibérément (#114), et trancher au hasard rouvrirait ce que ce choix
ferme — la commande rend donc la liste des candidats et refuse d'agir.

**Deux contournements délibérés, à ne pas prendre pour des oublis** : elle
n'applique pas la non-amplification (sans session, il n'y a pas d'acteur dont
comparer les pouvoirs — l'accès au serveur *est* le privilège) et n'est pas
soumise à l'invariant du dernier administrateur (elle ne fait qu'accorder, donc
elle ne peut pas verrouiller).

## `allow-email` — autoriser une adresse (#170)

```bash
uv run python -m app.cli allow-email --email <adresse>
```

La liste des adresses autorisées à ouvrir une session vit en base et s'édite
depuis `/admin/acces`. Cette commande est la **voie d'amorçage**, jumelle de
`grant-role` : sur une base neuve la liste est vide, donc personne ne peut se
connecter, donc personne ne peut ouvrir l'écran qui inscrirait la première
adresse.

Idempotente. Codes de sortie : `0` (inscrite **ou** déjà présente), `2` sur une
adresse mal formée — rien n'est alors écrit. Pas de `--json` : ce n'est pas un
batch. La validation passe par le **même service** que la ressource HTTP
(`services/auth/allowed_emails.validate_email`), deux notions de « adresse
valide » divergeant au premier ajustement. Et par le service, **pas** par le DTO
`AllowedEmailCreate`, qui reste en `str` délibérément : une contrainte Pydantic
sur le champ ferait rendre à FastAPI son 422 par défaut, dont le `detail` est une
liste d'objets et le message anglais — soit FR-010 et la forme
`{"detail": "<chaîne>"}` rompues d'un coup.

Elle mentionne les comptes qu'elle **rouvre** (« 2 compte(s) réactivé(s) ») :
retirer une adresse désactive les comptes qui la portent, et la réinscrire les
réactive. Sans ce compte rendu, « rien à faire » ne se distinguerait pas de
« j'ai rouvert deux accès ».

**Elle ne retire pas**, et ce n'est pas un oubli : le retrait vit dans l'écran,
où il est gardé par l'invariant du dernier administrateur. Une commande de
retrait sans cet invariant serait un verrou à distribuer, et l'erreur qu'elle
rendrait possible — se fermer soi-même l'accès — n'a pas de rattrapage plus
simple que celui qu'elle prétendrait offrir.

**Elle ne crée pas d'utilisateur.** L'amorçage complet tient en trois gestes :
`allow-email`, une **connexion** par le navigateur (c'est elle qui crée le
compte), puis `grant-role --role admin`.

## `revoke-sessions` — la révocation d'urgence (#169)

```bash
uv run python -m app.cli revoke-sessions --all [--yes]
uv run python -m app.cli revoke-sessions --email <adresse>
```

**Deux besoins avaient été fondus, et c'est ce que cette commande sépare.**
Purger les sessions *expirées* reste opportuniste (`session.open_for`), et un
ordonnanceur y serait du théâtre — le dépôt n'en a aucun. Révoquer *en urgence*
n'arrive jamais, sauf le jour où : la procédure d'avant supposait d'ouvrir `psql`
sur Supabase à la main, sous stress, en production.

Deux cibles **exclusives** l'une de l'autre — deux modes, pas des filtres à
composer, même parti pris que `rescrape-db` —, et **aucune n'est le défaut** : un
`revoke-sessions` nu qui déconnecterait tout le club serait le pire des défauts
imaginables (code 2). `--yes` ne garde que `--all` : fermer les sessions d'une
personne se répare par une reconnexion, celles de tout le club non, et c'est le
seul des deux gestes qui déconnecte aussi celui qui le lance. Un refus interactif
sort en **0** avec « Annulé. » — annuler n'est pas une panne, précédent
`reset_db.py`. Sans terminal (cron, CI, `< /dev/null`), `--all` sans `--yes`
sort en **1** sur l'`Abort` de Click : rien n'est écrit, et un batch qui ne
confirme pas doit s'entendre dire qu'il n'a rien fait.

Pas de `--json` : ce n'est pas un batch. Le bilan compte **deux unités**, et
chaque nom le dit : « N session(s) fermée(s) sur M compte(s) ». Les deux ne
comptent que le **vivant** — session non expirée, compte actif, soit le filtre
exact de `session.resolve` —, alors que la suppression, elle, emporte aussi les
lignes mortes. L'écart est délibéré : les effacer est de l'hygiène gratuite, les
annoncer serait un mensonge. Faute d'ordonnanceur, une base réelle est pleine de
lignes expirées, et « 5 sessions fermées » quand une seule était vivante
empêcherait de répondre à la seule question qu'on se pose en incident.

**Une adresse qu'aucun compte ne porte est une erreur d'usage** (code 2), et une
adresse mal formée aussi — par `allowed_emails.validate_email`, le **même**
service que l'écran et qu'`allow-email`. « 0 session fermée » reste un compte
rendu juste pour `--all` et pour une adresse connue sans session ouverte ; sur
une faute de frappe, il confondrait « rien à fermer » et « vous avez mal tapé »,
au moment exact où l'exploitant a besoin de croire ce qu'il lit. Même refus que
`grant-role`, sur la même liste rendue par `find_by_email`.

**Sur `--email`, elle prend tous les comptes portant l'adresse.** `users.email`
n'est pas unique (#114, FR-003) : là où `grant-role` refuse de trancher entre les
candidats et rend la liste, la révocation les prend tous — sous incident, en
épargner un serait l'erreur coûteuse.

**Elle ne désactive aucun compte**, et c'est ce qui la distingue du retrait d'une
adresse autorisée (#170). Le retrait ferme par la **jointure** (`is_active =
False`) et laisse les lignes de `user_sessions` : une réinscription dans la
fenêtre de TTL ressuscite les jetons exacts, appareil oublié compris. La
révocation **supprime** les lignes et laisse les comptes ouverts — on coupe des
jetons, on ne met personne dehors, et les intéressés se reconnectent.

**Elle a un jumeau dans le back-office** (pouvoir `sessions:revoke`), et la
redondance est le but : le back-office est ergonomique là où l'exploitant est
déjà connecté, la CLI reste praticable le jour où c'est justement du back-office
qu'on se méfie. Le jumeau porte les **deux** portées, et les deux vivent dans
`/admin/acces` : « Fermer les sessions » par ligne pour une adresse, une carte
en bas de page pour tout le club. Même cible que la CLI — l'écran liste des
**adresses**, pas des comptes, et frappe donc tous ceux qui la portent. Un
second écran pour un unique bouton aurait coûté une entrée de navigation de
plus.

**Ordre d'exploitation à connaître** : une adresse retirée disparaît de la
liste, donc ses sessions ne sont plus fermables depuis l'écran. Fermer d'abord,
retirer ensuite — ou passer par la CLI, qui n'a pas besoin que l'adresse soit
encore autorisée.
