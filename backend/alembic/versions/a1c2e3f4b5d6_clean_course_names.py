"""nettoie les noms d'épreuve : espaces superflus et enrobage i18n RaceResult (#1088)

Revision ID: a1c2e3f4b5d6
Revises: 9f2e3d4c5b6a
Create Date: 2026-09-26 13:30:00.000000

Les scrapers et la saisie manuelle nettoient désormais le nom à l'entrée. Le
nom faisant partie de l'identité `(name, event_date, event_type, is_relay)`,
une épreuve déjà stockée sous sa forme sale serait recréée en doublon au
prochain rescrape : on la renomme ici, sauf si la forme propre existe déjà
(collision laissée à l'administration, jamais fusionnée en silence).

Résolution i18n volontairement recopiée plutôt qu'importée de
`app.scrapers.raceresult` : une migration fige son comportement.
"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c2e3f4b5d6'
down_revision: Union[str, None] = '9f2e3d4c5b6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_I18N = re.compile(r"\{([A-Za-z]{2}:[^{}|]*(?:\|[A-Za-z]{2}:[^{}|]*)*)\}")
# Un nom qualifié par `qualify_event_name` : « <événement> - <qualifiant> ».
_QUALIFIE = re.compile(r"^(?P<evenement>.*?)\s+-\s+(?P<qualifiant>.*)$")


def _variante(match: re.Match) -> str:
    variantes = {}
    for part in match.group(1).split("|"):
        cle, _, valeur = part.partition(":")
        variantes[cle.upper()] = valeur.strip()
    choix = variantes.get("FR") or variantes.get("EN") or next(
        (v for v in variantes.values() if v), ""
    )
    # Toutes variantes vides : laissé intact, comme `_label_i18n` au runtime.
    return choix or match.group(0)


def _propre(nom: str) -> str:
    propre = " ".join(_I18N.sub(_variante, nom).split())
    # Même règle que `qualify_event_name` : un qualifiant déjà contenu dans le
    # nom d'événement n'est pas ré-ajouté, sans quoi le rescrape suivant
    # produirait un autre nom, donc une autre épreuve.
    if _I18N.search(nom) and (m := _QUALIFIE.match(propre)):
        if m["qualifiant"].lower() in m["evenement"].lower():
            return m["evenement"]
    return propre


def upgrade() -> None:
    connexion = op.get_bind()
    lignes = connexion.execute(
        sa.text("SELECT id, name, event_date, event_type, is_relay FROM courses")
    ).fetchall()
    identites = {(nom, jour, type_, relais) for _, nom, jour, type_, relais in lignes}
    for id_, nom, jour, type_, relais in lignes:
        propre = _propre(nom)
        if propre == nom or (propre, jour, type_, relais) in identites:
            continue
        connexion.execute(
            sa.text("UPDATE courses SET name = :nom WHERE id = :id"), {"nom": propre, "id": id_}
        )
        identites.add((propre, jour, type_, relais))


def downgrade() -> None:
    # Irréversible par nature : la forme sale n'est pas conservée, et rien ne
    # la réclame.
    pass
