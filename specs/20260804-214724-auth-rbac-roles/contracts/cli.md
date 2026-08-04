# Contrat CLI — `grant-role`

**Feature** : RBAC — rôles composables · **Révisé** : 2026-08-04 (v2)

```bash
uv run python -m app.cli grant-role --email <adresse> --role <slug> [--organisation <slug>]
```

C'est la voie d'amorçage (FR-027) : sur une installation neuve, aucun
administrateur n'existe et les ressources qui distribuent les rôles exigent
elles-mêmes un pouvoir. C'est aussi **le seul rattrapage hors ligne** si
l'installation se retrouve sans administrateur par un chemin que l'application ne
contrôle pas.

`--role` prend le **slug** d'un rôle existant, pas un nom d'affichage : c'est le
seul identifiant de rôle immuable (`data-model.md`). Les rôles semés par la
migration sont `admin` et `validator` ; tout rôle créé ensuite depuis l'API est
également utilisable.

`--organisation` vaut par défaut l'unique organisation semée. L'option existe
parce que le modèle porte l'organisation ; elle n'a qu'une valeur possible tant
qu'un second club n'est pas créé.

## Ce qu'elle ne fait pas

**Elle ne crée pas d'utilisateur** (FR-028) : un utilisateur naît d'une connexion
réussie et autorisée, son identité venant du fournisseur. Une adresse inconnue
est une erreur d'usage — pas une invitation à créer un compte fantôme.

**Elle ne crée pas de rôle.** Composer un rôle est un geste d'administration, il
passe par l'API (et, plus tard, par un écran). La CLI n'existe que pour le cas où
l'API est inatteignable faute d'administrateur.

## Sorties et codes de retour

Rapport texte sur **stdout**, logs sur **stderr** (`configure_cli_logging`).
Pas de `--json` : ce n'est pas un batch, il n'y a pas de bilan à piper.

| Cas | Code | Sortie |
| --- | --- | --- |
| Rôle attribué | `0` | `Rôle « Administrateur » attribué à Prénom Nom (id=3, adresse@example.org) dans « Triathlon Club Nantais ».` |
| Rôle déjà porté | `0` | `Rien à faire : Prénom Nom (id=3) porte déjà ce rôle.` |
| Adresse inconnue | `2` | Explique qu'un utilisateur naît d'une connexion, et rappelle que l'adresse doit d'abord figurer dans `AUTH_ALLOWED_EMAILS`. |
| Adresse ambiguë | `2` | Liste les candidats : identifiant, nom affiché, fournisseur, date de création. |
| Slug de rôle inconnu | `2` | Nomme les rôles existants. |
| Rôle propre à une autre organisation | `2` | Nomme l'organisation à laquelle il appartient. |

Le `2` suit la convention Click / Typer pour l'erreur d'usage, comme
`--provider` inconnu dans `rescrape-db` (`AGENTS.md`, table des codes de sortie).

## L'adresse ambiguë n'est pas un cas d'école

`users.email` **n'est pas unique**, délibérément : deux identités externes
portant la même adresse donnent deux utilisateurs distincts (#114, FR-003,
documenté dans `models/user.py`). Apparier sur l'adresse rouvrirait la prise de
contrôle par pré-inscription.

La commande refuse donc d'agir au hasard (FR-030) et rend de quoi trancher.
Départager se fait ensuite par identifiant, via l'API, une fois un premier
administrateur en place.

## Ce qu'elle contourne délibérément

`grant-role` **n'applique pas** la règle de non-amplification (FR-011) : elle
s'exécute sur le serveur, sans session, et il n'y a donc pas d'acteur dont on
puisse comparer les pouvoirs. C'est assumé — c'est précisément ce qui en fait le
rattrapage universel. L'accès au serveur *est* le privilège.

Elle **n'est pas soumise** non plus à l'invariant du dernier administrateur : elle
ne fait qu'accorder, jamais retirer, donc elle ne peut pas verrouiller.

## Journalisation

Une attribution est journalisée comme celles de l'API (FR-033) : acteur — ici, la
ligne de commande —, cible, rôle, sens. En anglais, sur stderr.

## Nommage

`grant-role`, pas `create-admin` (proposé par l'issue #115). La commande ne
*crée* rien, et *l'*administrateur n'est pas unique. Le nom retenu décrit le
geste, couvre tous les rôles présents et à venir, et porte déjà son
`--organisation`.
