"""Las pruebas nunca deben arrancar un trabajador conectado al proyecto real."""
import pytest


@pytest.fixture(autouse=True)
def trabajador_real_desactivado(monkeypatch):
    # Los tests específicos del ciclo de vida activan explícitamente un doble.
    monkeypatch.setenv('TRABAJADOR_AUTOMATICO', 'false')
