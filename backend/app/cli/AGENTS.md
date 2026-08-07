# Sorties de la CLI (stdout parsable)

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
| `2` | **Erreur d'usage** (convention Click) : option invalide — notamment `--provider` / `--only-provider` inconnu, rejeté avant tout travail par `cli/validators`. |
| `130` | Ctrl-C. **Prioritaire sur 1** : une interruption est une action de l'opérateur, pas une panne. |

Un tube fermé (`… | head -2`) ne fausse aucun de ces codes : le `BrokenPipeError`
est rattrapé, et le bilan bascule sur stderr plutôt que d'être perdu.

**Vocabulaire** : la CLI compte des **épreuves** (une `source_url` unique), jamais
des courses. Une épreuve porte N `Course` en base (heats Breizh Chrono, variantes
individuel/relais) : `rescrape-db` dédoublonne par `source_url` avant le batch,
donc « Épreuves ciblées : 12 » sur une table de 53 courses n'est pas une perte.

**Deux modes de sélection pour `rescrape-db`**, exclusifs l'un de l'autre :
par filtre sur la base (`--provider`, `--older-than`), ou par URL explicite
(`--url`, répétable, et `--urls-from <fichier|->`). Le second **court-circuite
la base** : une URL inconnue en table `course` est scrapée normalement, sans
avertissement — c'est le cas nominal du rejeu d'un échec d'import, dont
l'épreuve n'a rien persisté. Les combiner est une erreur d'usage (code 2) : ce
sont deux modes, pas des filtres à composer. `--limit` reste compatible avec les
deux : il borne la liste finale, il ne sélectionne rien.

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
