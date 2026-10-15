"""Collecte des URLs ciblées par la CLI (`--url`, `--urls-from`).

Distinct de `validators.py`, qui ne valide que des saisies déjà en mémoire :
collecter des URLs suppose en plus de **lire** — un fichier, ou stdin. Assez
pour justifier un module à part, minuscule et testable isolément.

Toute saisie invalide est rejetée par `typer.BadParameter` : message + usage sur
stderr, code de sortie 2 (convention Click), arrêt **avant** l'ouverture de la
Session. Même raisonnement que `validate_provider`.
"""
import click
import typer

from app.services import sheet_source


def _file_lines(path: str) -> list[str]:
    """Lit `path`, ou **stdin** si `path` vaut `-`.

    `click.open_file` gère nativement le tiret = stdin et, avec
    `encoding="utf-8-sig"`, retire un BOM en tête (export Notepad/Excel
    Windows) — fichier comme stdin —, sans rien changer sur une entrée sans BOM.
    """
    try:
        with click.open_file(path, encoding="utf-8-sig") as f:
            return f.read().splitlines()
    except UnicodeDecodeError as exc:
        # Hérite de ValueError, pas de OSError (pas de `strerror`) : bloc à part,
        # avec un message qui pointe l'encodage plutôt que de laisser filer une
        # trace Python brute.
        raise typer.BadParameter(
            f"fichier d'URLs illisible : « {path} » n'est pas encodé en UTF-8 ({exc})."
        ) from exc
    except OSError as exc:
        raise typer.BadParameter(
            f"fichier d'URLs illisible : « {path} » ({exc.strerror})."
        ) from exc


def _validate_line(line: str, origin: str) -> None:
    if not line.startswith(("http://", "https://")):
        raise typer.BadParameter(f"{origin} n'est pas une URL http(s) : « {line} ».")


def load_urls(urls: list[str] | None, urls_from: str | None) -> list[str] | None:
    """Concatène les `--url` répétés puis le contenu de `--urls-from`.

    Renvoie `None` quand **aucun** ciblage n'a été demandé — à distinguer d'une
    liste **vide** (fichier vide, ou liste d'échecs vide en fin de boucle de
    rejeu), qui signifie « zéro épreuve à traiter » et doit sortir en 0. Les
    confondre ferait retomber `--urls-from vide.txt` sur le mode base, qui
    re-scraperait toute la table en silence.

    Les deux options se cumulent : ajouter une URL à une liste est un besoin
    légitime. `--url` est répétable, `--urls-from` ne l'est pas — une seule
    source de liste, `cat a.txt b.txt | … --urls-from -` couvre le reste.

    Lignes vides et lignes commençant par `#` ignorées : un opérateur qui
    construit sa liste à la main commente une URL plutôt que de la supprimer.
    Toute autre ligne non-http(s) est rejetée **en citant son numéro de ligne**,
    corrigeable sans relire le fichier à l'œil.

    Dédup finale via `sheet_source.dedupe_links` : ordre et forme d'origine
    conservés, clé `normalize_url` — la même que partout ailleurs.
    """
    urls = urls or []
    if not urls and urls_from is None:
        return None

    collected: list[str] = []
    for value in urls:
        line = value.strip()
        _validate_line(line, "--url")
        collected.append(line)

    if urls_from is not None:
        for line_number, raw in enumerate(_file_lines(urls_from), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            _validate_line(line, f"--urls-from, ligne {line_number}")
            collected.append(line)

    return sheet_source.dedupe_links(collected)


def validate_single_heat(
    *, single_heat: bool, url: list[str], urls_from: str | None,
    provider: str | None, older_than: int | None,
) -> None:
    """Refuse `--single-heat` sans `--url` ou avec des filtres de base (issue #156).

    `--single-heat` est une **échappatoire** ciblée : elle ne s'applique qu'à des
    URLs explicites (obligatoirement porteuses de `?heat=X` — la validation
    d'URL individuelle est différée à l'import lui-même). Elle ne se combine
    pas à `--provider` / `--older-than` (filtres de base), pour la même raison
    que `validate_exclusive_targeting` : ce sont deux modes disjoints.
    """
    if not single_heat:
        return
    if not url and urls_from is None:
        raise typer.BadParameter(
            "--single-heat exige --url (ou --urls-from) avec un paramètre ?heat= : "
            "c'est une échappatoire ciblée, pas un mode de filtrage de la base."
        )
    conflicting = [
        f for f, cond in (("--provider", provider is not None),
                          ("--older-than", older_than is not None))
        if cond
    ]
    if conflicting:
        raise typer.BadParameter(
            f"--single-heat est exclusif de {' et '.join(conflicting)} : "
            "l'échappatoire ne cible que des URLs explicites."
        )
    for u in url:
        if "heat=" not in u:
            raise typer.BadParameter(
                f"--single-heat exige ?heat= dans chaque URL : « {u} » n'en porte pas."
            )


def validate_exclusive_targeting(
    *, url: list[str], urls_from: str | None, provider: str | None, older_than: int | None
) -> None:
    """Refuse un ciblage par URL combiné à `--provider` ou `--older-than`.

    Ce sont deux **modes de sélection**, pas des filtres à composer : `--url`
    court-circuite la base (c'est tout l'intérêt du rejeu d'un échec d'import,
    dont l'épreuve n'est jamais persistée), tandis que `--provider` et
    `--older-than` filtrent ce que la base contient. Les combiner produirait un
    ET dont personne ne peut prédire le résultat.

    Prend les paramètres **bruts** de la commande (`url`, `urls_from`), pas le
    résultat de `load_urls` : un ciblage est demandé dès que `--url` est
    non vide ou `--urls-from` est renseigné, sans avoir besoin de lire quoi
    que ce soit (fichier ou stdin) pour le savoir. C'est ce qui permet
    d'appeler cette validation **avant** `load_urls` — sinon
    `--urls-from -` combiné à une option incompatible bloquerait en attente
    d'une saisie stdin qui sera de toute façon rejetée.

    Vérification croisée, donc appelée explicitement en tête de commande : un
    callback Typer ne voit que sa propre option.
    """
    if not url and urls_from is None:
        return
    conflicting = []
    if provider is not None:
        conflicting.append("--provider")
    if older_than is not None:
        conflicting.append("--older-than")
    if conflicting:
        raise typer.BadParameter(
            f"--url / --urls-from est exclusif de {' et '.join(conflicting)} : "
            "ce sont deux modes de sélection, pas des filtres à composer."
        )
