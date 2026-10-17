"""Fronteras de la exportación V6: no copiar secretos/rutas externas ni sobrescribir."""
import hashlib

import pytest

from scripts import auditar_entrega as entrega


@pytest.mark.parametrize('nombre', [
    '../privado.txt', '/fuera.txt', 'C:/fuera.txt', 'carpeta\\fuera.txt',
    '.env', 'frontend/.env.local', 'secreto.pem', '.git/config', '.venv/python.exe',
])
def test_archivos_privados_y_escapes_no_son_exportables(tmp_path, monkeypatch, nombre):
    monkeypatch.setattr(entrega, 'RAIZ', tmp_path)
    with pytest.raises(ValueError):
        entrega.ruta_publicable(nombre)


def test_ejemplo_publico_admitido_y_archivo_ausente_rechazado(tmp_path, monkeypatch):
    monkeypatch.setattr(entrega, 'RAIZ', tmp_path)
    ejemplo = tmp_path/'.env.example'
    ejemplo.write_text('SUPABASE_URL=\n', encoding='utf-8')
    assert entrega.ruta_publicable('.env.example') == ejemplo
    with pytest.raises(ValueError):
        entrega.ruta_publicable('ausente.md')


def test_consolidacion_conserva_fuentes_hashes_y_no_sobrescribe(tmp_path, monkeypatch):
    monkeypatch.setattr(entrega, 'RAIZ', tmp_path)
    carpeta = tmp_path/'docs'/'bitacora_ia'
    carpeta.mkdir(parents=True)
    fuentes = {}
    for nombre in ('emilia', 'jose', 'noel'):
        texto = f'# {nombre}\n\n| Uso | Revisión |\n| IA | Pendiente, sin acreditación remota |\n'
        ruta = carpeta/f'{nombre}.md'
        ruta.write_text(texto, encoding='utf-8')
        fuentes[ruta] = ruta.read_bytes()
    destino = tmp_path/'consolidada.md'
    entrega.consolidar_bitacoras(destino)
    resultado = destino.read_text(encoding='utf-8')
    for ruta, contenido in fuentes.items():
        assert ruta.read_bytes() == contenido
        assert contenido.decode('utf-8').replace('\r\n', '\n').rstrip() in resultado
        assert hashlib.sha256(contenido).hexdigest() in resultado
    previo = destino.read_bytes()
    with pytest.raises(FileExistsError):
        entrega.consolidar_bitacoras(destino)
    assert destino.read_bytes() == previo
