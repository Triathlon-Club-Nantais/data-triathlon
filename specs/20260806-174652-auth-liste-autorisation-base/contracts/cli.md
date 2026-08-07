# Contrat CLI — `allow-email`

**Feature** : liste d'autorisation en base · **Créé** : 2026-08-06

```bash
uv run python -m app.cli allow-email --email <adresse>
```

La **voie d'amorçage** (FR-014), jumelle de `grant-role`. Sur une installation
neuve, la liste est vide : personne ne peut ouvrir de session, donc personne ne
peut ouvrir le back-office pour autoriser quelqu'un. Cette commande rompt le
cercle. C'est aussi le rattrapage hors ligne si l'écran devient inaccessible.

Elle **contourne délibérément la garde de pouvoir**, exactement comme
`grant-role` : sans session, il n'y a pas d'acteur dont comparer les pouvoirs,
et l'accès au serveur *est* le privilège.

## L'amorçage complet tient en deux commandes

```bash
uv run python -m app.cli allow-email --email vous@exemple.fr   # 1. autoriser
# → se connecter une fois par le navigateur : c'est la connexion qui crée l'utilisateur
uv run python -m app.cli grant-role --email vous@exemple.fr --role admin   # 2. habiliter
```

L'ordre n'est pas interchangeable : `grant-role` **ne crée pas d'utilisateur**,
et un utilisateur naît d'une connexion réussie *et autorisée*. Le message
d'erreur de `grant-role` pour adresse inconnue doit donc renvoyer vers
`allow-email` — il cite aujourd'hui `AUTH_ALLOWED_EMAILS`, qui n'existera plus.

## Ce qu'elle ne fait pas

**Elle ne retire pas.** Le retrait vit dans l'écran, où il est gardé par
l'invariant du dernier administrateur (`contracts/admin-api.md`). Une commande de
retrait sans cet invariant serait un verrou à distribuer, et l'erreur qu'elle
rendrait possible — se fermer soi-même l'accès — n'a aucun rattrapage plus simple
que celui qu'elle prétendrait offrir. Réinscrire une adresse suffit à réparer un
retrait fait par erreur.

**Elle ne crée pas d'utilisateur.** Comme `grant-role` : autoriser une adresse
n'est pas créer un compte. Le compte naît de la première connexion.

## Sorties et codes de retour

Rapport texte sur **stdout**, logs sur **stderr** (`configure_cli_logging`).
Pas de `--json` : ce n'est pas un batch, il n'y a pas de bilan à piper — même
raisonnement que `grant-role`.

| Cas | Code | Sortie |
| --- | --- | --- |
| Adresse inscrite | `0` | `Adresse « contributeur@exemple.fr » autorisée à ouvrir une session.` |
| Adresse déjà présente | `0` | `Rien à faire : « contributeur@exemple.fr » est déjà autorisée.` |
| Adresse réinscrite alors que des comptes étaient fermés | `0` | Ajoute `2 compte(s) réactivé(s).` |
| Adresse mal formée | `2` | Nomme la saisie et rappelle la forme attendue. Rien n'est écrit. |

Le `2` suit la convention Click / Typer pour l'erreur d'usage, comme
`--provider` inconnu dans `rescrape-db` (`AGENTS.md`, table des codes de sortie).

## Normalisation, comme partout

L'adresse est mise en minuscules et débarrassée de ses espaces de bordure avant
écriture. `--email " Vous@Exemple.FR "` inscrit `vous@exemple.fr`, et une seconde
exécution avec l'une ou l'autre forme rend « rien à faire ».
