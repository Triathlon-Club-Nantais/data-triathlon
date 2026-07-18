"""Collecte des URLs ciblées par la CLI (`--url`, `--urls-from`).

Distinct de `validators.py`, qui ne valide que des saisies déjà en mémoire :
collecter des URLs suppose en plus de **lire** — un fichier, ou stdin. Assez
pour justifier un module à part, minuscule et testable isolément.

Toute saisie invalide est rejetée par `typer.BadParameter` : message + usage sur
stderr, code de sortie 2 (convention Click), arrêt **avant** l'ouverture de la
Session. Même raisonnement que `valider_provider`.
"""
import sys
from pathlib import Path

import typer

from app.services import sheet_source


def _lignes_du_fichier(chemin: str) -> list[str]:
    """Lit `chemin`, ou **stdin** si `chemin` vaut `-` (pas de fichier temporaire)."""
    if chemin == "-":
        return sys.stdin.read().splitlines()
    try:
        # utf-8-sig : retire un BOM en tête (export Notepad/Excel Windows) sans
        # rien changer pour un fichier UTF-8 sans BOM.
        return Path(chemin).read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        # Hérite de ValueError, pas de OSError (pas de `strerror`) : bloc à part,
        # avec un message qui pointe l'encodage plutôt que de laisser filer une
        # trace Python brute.
        raise typer.BadParameter(
            f"fichier d'URLs illisible : « {chemin} » n'est pas encodé en UTF-8 ({exc})."
        ) from exc
    except OSError as exc:
        raise typer.BadParameter(
            f"fichier d'URLs illisible : « {chemin} » ({exc.strerror})."
        ) from exc


def _valider_ligne(ligne: str, origine: str) -> None:
    if not ligne.startswith(("http://", "https://")):
        raise typer.BadParameter(f"{origine} n'est pas une URL http(s) : « {ligne} ».")


def charger_urls(urls: list[str] | None, urls_from: str | None) -> list[str] | None:
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

    collectees: list[str] = []
    for valeur in urls:
        ligne = valeur.strip()
        _valider_ligne(ligne, "--url")
        collectees.append(ligne)

    if urls_from is not None:
        for numero, brute in enumerate(_lignes_du_fichier(urls_from), start=1):
            ligne = brute.strip()
            if not ligne or ligne.startswith("#"):
                continue
            _valider_ligne(ligne, f"--urls-from, ligne {numero}")
            collectees.append(ligne)

    return sheet_source.dedupe_links(collectees)


def valider_ciblage_exclusif(
    *, urls: list[str] | None, provider: str | None, older_than: int | None
) -> None:
    """Refuse un ciblage par URL combiné à `--provider` ou `--older-than`.

    Ce sont deux **modes de sélection**, pas des filtres à composer : `--url`
    court-circuite la base (c'est tout l'intérêt du rejeu d'un échec d'import,
    dont l'épreuve n'est jamais persistée), tandis que `--provider` et
    `--older-than` filtrent ce que la base contient. Les combiner produirait un
    ET dont personne ne peut prédire le résultat.

    Vérification croisée, donc appelée explicitement en tête de commande : un
    callback Typer ne voit que sa propre option.
    """
    if urls is None:
        return
    incompatibles = []
    if provider is not None:
        incompatibles.append("--provider")
    if older_than is not None:
        incompatibles.append("--older-than")
    if incompatibles:
        raise typer.BadParameter(
            f"--url / --urls-from est exclusif de {' et '.join(incompatibles)} : "
            "ce sont deux modes de sélection, pas des filtres à composer."
        )
