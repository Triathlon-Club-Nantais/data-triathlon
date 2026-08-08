"""Lecture d'un fichier téléversé — CSV ou XLSX (#47).

Aucun fichier sur disque : les classeurs sont fabriqués en mémoire par
`openpyxl`, comme ils le seront en production — le fichier n'est jamais écrit
côté serveur (FR-011).
"""
import io

import pytest
from openpyxl import Workbook

from app.services import sheet_source

LIEN = "https://www.klikego.com/resultats/une-course"
AUTRE = "https://www.protiming.fr/Resultats/course"


def _xlsx(lignes: list[list]) -> bytes:
    """Un classeur en mémoire, à la forme que produirait un export réel."""
    classeur = Workbook()
    feuille = classeur.active
    for ligne in lignes:
        feuille.append(ligne)
    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


def _csv(texte: str) -> bytes:
    return texte.encode("utf-8")


# ── read_table ───────────────────────────────────────────────────────────────


def test_un_csv_est_lu_en_lignes():
    contenu = _csv(f"Nom,Lien\nCourse A,{LIEN}\n")

    entetes, lignes = sheet_source.read_table(contenu, "epreuves.csv")

    assert entetes == ["Nom", "Lien"]
    assert lignes == [["Course A", LIEN]]


def test_un_xlsx_est_lu_de_la_meme_facon():
    contenu = _xlsx([["Nom", "Lien"], ["Course A", LIEN]])

    entetes, lignes = sheet_source.read_table(contenu, "epreuves.xlsx")

    assert entetes == ["Nom", "Lien"]
    assert lignes == [["Course A", LIEN]]


def test_une_cellule_vide_d_un_xlsx_devient_une_chaine_vide():
    """`openpyxl` rend `None`, jamais `""`. Laisser passer un `None` ferait
    tomber le comptage de liens sur `.startswith`."""
    contenu = _xlsx([["Nom", "Lien"], ["Course A", None]])

    _, lignes = sheet_source.read_table(contenu, "epreuves.xlsx")

    assert lignes == [["Course A", ""]]


def test_un_nombre_d_un_xlsx_est_ramene_a_du_texte():
    contenu = _xlsx([["Dossard", "Lien"], [42, LIEN]])

    _, lignes = sheet_source.read_table(contenu, "epreuves.xlsx")

    assert lignes == [["42", LIEN]]


@pytest.mark.parametrize("nom", ["epreuves.csv", "epreuves.xlsx"])
def test_un_en_tete_vide_est_nomme_par_son_rang(nom):
    """« Colonne 3 » plutôt qu'une case vide dans le sélecteur : une colonne
    qu'on ne peut pas nommer est une colonne qu'on ne peut pas désigner."""
    contenu = (
        _csv(f"Nom,,Lien\nCourse A,x,{LIEN}\n")
        if nom.endswith(".csv")
        else _xlsx([["Nom", None, "Lien"], ["Course A", "x", LIEN]])
    )

    entetes, _ = sheet_source.read_table(contenu, nom)

    assert entetes == ["Nom", "Colonne 2", "Lien"]


def test_un_fichier_vide_ne_rend_aucune_colonne():
    entetes, lignes = sheet_source.read_table(_csv(""), "vide.csv")

    assert entetes == []
    assert lignes == []


def test_une_extension_inconnue_est_refusee():
    with pytest.raises(sheet_source.UnsupportedFileError):
        sheet_source.read_table(_csv("x"), "epreuves.pdf")


def test_un_classeur_illisible_est_nomme():
    """Un `.xlsx` qui n'en est pas un : l'erreur doit dire « fichier illisible »
    et non remonter la trace d'`openpyxl`."""
    with pytest.raises(sheet_source.UnreadableFileError):
        sheet_source.read_table(b"ceci n'est pas un classeur", "epreuves.xlsx")


def test_un_csv_en_latin1_reste_lisible():
    """Les exports d'un tableur français arrivent souvent en cp1252. Échouer
    sur un accent rendrait l'écran inutilisable un jour sur deux."""
    contenu = f"Nom,Lien\nCourse à Nantes,{LIEN}\n".encode("cp1252")

    _, lignes = sheet_source.read_table(contenu, "epreuves.csv")

    assert lignes[0][0] == "Course à Nantes"


# ── links_in_column ──────────────────────────────────────────────────────────


def test_les_liens_d_une_colonne_sont_extraits():
    lignes = [["A", LIEN], ["B", AUTRE]]

    resultat = sheet_source.links_in_column(lignes, 1)

    assert resultat.links == [LIEN, AUTRE]


def test_une_valeur_qui_n_est_pas_une_url_est_comptee_a_part():
    """Elle n'est ni un succès ni un échec : la ligne existe, elle ne porte
    simplement pas de lien. Le rapport la nomme `rows_without_link`."""
    lignes = [["A", LIEN], ["B", "à venir"], ["C", ""]]

    resultat = sheet_source.links_in_column(lignes, 1)

    assert resultat.links == [LIEN]
    # La ligne vide n'en fait pas partie : elle ne dit rien, l'autre si.
    assert resultat.rows_without_link == 1


def test_un_doublon_ne_compte_qu_une_epreuve():
    lignes = [["A", LIEN], ["B", LIEN + "/"], ["C", AUTRE]]

    resultat = sheet_source.links_in_column(lignes, 1)

    assert resultat.links == [LIEN, AUTRE]


def test_les_liens_sont_partages_entre_supportes_et_ignores():
    """Un lien dont aucun scraper ne reconnaît l'hôte n'est ni un succès ni un
    échec : il n'est jamais soumis, et l'écran doit le dire avant de lancer."""
    inconnu = "https://chrono-maison.example/resultats/42"
    lignes = [["A", LIEN], ["B", inconnu]]

    resultat = sheet_source.links_in_column(lignes, 1)

    assert resultat.supported == [LIEN]
    assert resultat.ignored_by_host == {"chrono-maison.example": 1}


def test_une_colonne_hors_bornes_ne_leve_pas():
    """Une ligne plus courte que les autres est ordinaire dans un export : elle
    ne porte pas de lien, elle ne fait pas tomber la lecture."""
    lignes = [["A"], ["B", LIEN]]

    resultat = sheet_source.links_in_column(lignes, 1)

    assert resultat.links == [LIEN]


def test_le_comptage_par_colonne_sert_la_presuggestion():
    lignes = [["A", LIEN, "x"], ["B", AUTRE, "y"]]

    assert sheet_source.links_in_column(lignes, 0).count == 0
    assert sheet_source.links_in_column(lignes, 1).count == 2
    assert sheet_source.links_in_column(lignes, 2).count == 0
