"""Refus des placeholders `...` redondants dans `app/` (`py/ineffectual-statement`).

Une méthode de `Protocol` dont la docstring tient lieu de corps n'a pas besoin
d'un `...` : la docstring **est** l'instruction, et le `...` qui la suit n'a
aucun effet. C'est le motif des 10 notes « Statement has no effect » de l'onglet
« Code quality » — une par méthode des trois `Protocol` du projet
(`services/progress.py`, `services/auth/idp/base.py`, `scrapers/registry.py`).

**Ruff ne peut pas porter ce garde** : `PIE790` exempte délibérément les corps de
`Protocol`. Mesuré sur ruff 0.15.21 — sur une même sonde, la règle signale la
classe ordinaire et la fonction libre, jamais la méthode de `Protocol`. Les deux
outils sont en désaccord assumé sur ce motif, d'où ce méta-test, sur le patron du
détecteur AST de `test_core_http.py`.

Le `...` **seul** dans un corps est épargné : il en porte la syntaxe, le retirer
casserait le module. Seul le placeholder *redondant* est refusé.
"""
import ast
from pathlib import Path


def _placeholders_redondants(source: str) -> list[int]:
    """Lignes des `...` dont le corps porte déjà une autre instruction."""
    lignes: list[int] = []
    for noeud in ast.walk(ast.parse(source)):
        # `body` existe aussi sur `if`, `for`, `try`… : un `...` y est tout
        # autant sans effet. `IfExp.body` est une expression, d'où le filtre.
        corps = getattr(noeud, "body", None)
        if not isinstance(corps, list) or len(corps) < 2:
            continue
        lignes += [
            instruction.lineno
            for instruction in corps
            if isinstance(instruction, ast.Expr)
            and isinstance(instruction.value, ast.Constant)
            and instruction.value.value is Ellipsis
        ]
    return sorted(lignes)


def test_meta_aucun_placeholder_redondant_dans_app():
    racine = Path(__file__).resolve().parents[1] / "app"
    fautifs = [
        f"{chemin.relative_to(racine).as_posix()}:{ligne}"
        for chemin in sorted(racine.rglob("*.py"))
        for ligne in _placeholders_redondants(chemin.read_text(encoding="utf-8"))
    ]

    assert fautifs == [], (
        "Une docstring tient déjà lieu de corps : le `...` qui la suit est une "
        f"instruction sans effet (CodeQL `py/ineffectual-statement`). Sites : {fautifs}"
    )


def test_le_detecteur_voit_le_placeholder_apres_docstring():
    source = 'class P:\n    def m(self) -> bool:\n        """Doc."""\n        ...\n'
    assert _placeholders_redondants(source) == [4]


def test_le_detecteur_epargne_le_placeholder_seul():
    """Seul dans son corps, `...` porte la syntaxe : il n'est pas retirable."""
    assert _placeholders_redondants("def m() -> None:\n    ...\n") == []
    assert _placeholders_redondants("class P:\n    ...\n") == []


def test_le_detecteur_voit_le_placeholder_hors_signature():
    """Un `...` sans effet n'est pas propre aux corps de fonction."""
    assert _placeholders_redondants("if True:\n    x = 1\n    ...\n") == [3]
