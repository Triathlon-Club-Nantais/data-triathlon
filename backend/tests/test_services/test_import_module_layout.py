"""Le découpage d'`import_service` (#1186) : chaque symbole vit dans un seul module.

L'absence de l'ancien nom compte autant que la présence du nouveau :
`monkeypatch.setattr` lève sur un attribut absent, donc un test resté pointé sur
l'ancien module échoue au lieu de laisser passer le vrai scrape ou la vraie écriture.
"""
from app.services import import_persistence, import_service


def test_persistence_lives_in_import_persistence():
    assert callable(import_persistence.persist_steps)
    assert callable(import_persistence.persist_results)
    assert import_persistence.PassiveSource.__name__ == "PassiveSource"
    assert import_persistence.Reassignment.__name__ == "Reassignment"
    for name in (
        "persist_steps", "persist_results", "PassiveSource", "Reassignment",
        "_Persister", "_TRANCHE_SIZE", "split_relay_teammates", "mapping",
    ):
        assert not hasattr(import_service, name), name
