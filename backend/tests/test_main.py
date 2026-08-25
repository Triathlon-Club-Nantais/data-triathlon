"""Usine `create_app()` (#585 pour le dimensionnement du limiteur AnyIO)."""

from app.core.config import Settings
from app.main import _thread_limit_for


def test_thread_limit_for_reprend_la_capacite_totale_du_pool():
    """Le nombre de threads AnyIO suit `pool_size + max_overflow`, pas un
    défaut indépendant (#585) : c'était le déséquilibre mesuré — 40 threads
    pour 15 connexions au maximum, l'excédent attendant jusqu'à 30 s une
    connexion qui ne se libère jamais assez vite. Une seule source de vérité
    empêche les deux réglages de rediverger."""
    settings = Settings(db_pool_size=4, db_max_overflow=2)
    assert _thread_limit_for(settings) == 6
