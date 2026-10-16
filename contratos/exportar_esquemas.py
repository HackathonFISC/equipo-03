"""Desde la raíz: python -m contratos.exportar_esquemas. Útil para Noel."""
import importlib
import json
from pathlib import Path


def main():
    base = Path(__file__).resolve().parent
    manifest = json.loads((base / "ejemplos/manifest.json").read_text())
    salida = base / "esquemas"
    salida.mkdir(exist_ok=True)
    modelos = sorted(set(manifest.values()))
    for referencia in modelos:
        modulo, nombre = referencia.split(":")
        modelo = getattr(importlib.import_module(modulo), nombre)
        (salida / f"{nombre}.schema.json").write_text(
            json.dumps(modelo.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(f"{len(modelos)} esquemas exportados en {salida}")


if __name__ == "__main__":
    main()
