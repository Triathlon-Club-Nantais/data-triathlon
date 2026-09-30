"""Un module n'utilise pas les symboles `_privés` d'un service (#937).

Le re-scrape admin réimplémentait la persistance à partir de
`import_service._Persister`, et a divergé : il sautait les trois passes que les
autres chemins jouent avant la première ligne. La règle est tenue ici par un
méta-test, faute de quoi elle se perd à la modification suivante. Lecture par
`ast` : les mentions en docstring ou en commentaire ne comptent pas.
"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _service_aliases(tree: ast.Module) -> set[str]:
    """Noms locaux liés à un module de `app.services` dans ce fichier."""
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("app.services", "app.services.auth"):
            aliases.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app.services.") and alias.asname:
                    aliases.add(alias.asname)
    return aliases


def test_no_module_reaches_into_a_service_private_symbol():
    fautes = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _service_aliases(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and node.attr.startswith("_")
                and not node.attr.startswith("__")
            ):
                fautes.append(f"{path.relative_to(APP)}:{node.lineno} {node.value.id}.{node.attr}")
            elif (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("app.services.")
            ):
                fautes.extend(
                    f"{path.relative_to(APP)}:{node.lineno} {node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name.startswith("_")
                )

    assert not fautes, f"Symbole privé d'un service utilisé ailleurs : {fautes}"
