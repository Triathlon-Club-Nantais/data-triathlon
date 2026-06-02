import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests nécessitant un accès réseau réel (pytest -m integration)",
    )
