"""Pruebas de configuración y conexión sin credenciales ni red."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from comun.config import Configuracion, ErrorConfiguracion, cargar_configuracion
from comun.db import ErrorConexion, comprobar_conexion, crear_cliente, get_supabase, main

VALORES = {"SUPABASE_URL": "https://demo.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_sintetica"}


class ConfiguracionTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / ".env"

    def cargar(self, valores):
        return cargar_configuracion(self.ruta, entorno=valores)

    def test_no_requiere_gemini_telegram_ni_anon(self):
        self.assertEqual(self.cargar(VALORES).supabase_url, VALORES["SUPABASE_URL"])

    def test_falta_url(self):
        with self.assertRaisesRegex(ErrorConfiguracion, "Falta SUPABASE_URL"):
            self.cargar({})

    def test_falta_clave(self):
        with self.assertRaisesRegex(ErrorConfiguracion, "Falta SUPABASE_SERVICE_ROLE_KEY"):
            self.cargar({"SUPABASE_URL": VALORES["SUPABASE_URL"], "SUPABASE_ANON_KEY": "publica"})

    def test_repr_no_muestra_clave(self):
        self.assertNotIn(VALORES["SUPABASE_SERVICE_ROLE_KEY"], repr(self.cargar(VALORES)))

    def test_rechaza_url_invalida_sin_revelarla(self):
        for url in ["https://usuario:secreto@demo.supabase.co", "http://demo.supabase.co", "https://demo.supabase.co/rest/v1", "https://demo.supabase.co?clave=secreto", "https://demo.supabase.co:invalido", "https://demo supabase.co"]:
            with self.subTest(url=url), self.assertRaises(ErrorConfiguracion) as error:
                self.cargar({**VALORES, "SUPABASE_URL": url})
            self.assertNotIn(url, str(error.exception))

    def test_http_local_permitido(self):
        self.assertEqual(self.cargar({**VALORES, "SUPABASE_URL": "http://127.0.0.1:54321/"}).supabase_url, "http://127.0.0.1:54321")

    def test_rechaza_publishable(self):
        with self.assertRaisesRegex(ErrorConfiguracion, "publishable"):
            self.cargar({**VALORES, "SUPABASE_SERVICE_ROLE_KEY": "sb_publishable_prueba"})

    def test_dotenv_y_precedencia_entorno(self):
        self.ruta.write_text('SUPABASE_URL="https://archivo.supabase.co"\nSUPABASE_SERVICE_ROLE_KEY="sb_secret_${literal}"\n')
        self.assertEqual(self.cargar({}).supabase_service_role_key, "sb_secret_${literal}")
        self.assertEqual(self.cargar(VALORES).supabase_url, VALORES["SUPABASE_URL"])
        with self.assertRaises(ErrorConfiguracion):
            self.cargar({"SUPABASE_URL": ""})

    def test_ruta_por_defecto_en_raiz(self):
        self.ruta.write_text("\n".join(f"{k}={v}" for k, v in VALORES.items()))
        with patch("comun.config.RAIZ_PROYECTO", self.ruta.parent):
            self.assertEqual(cargar_configuracion(entorno={}).supabase_url, VALORES["SUPABASE_URL"])


class ConexionTests(unittest.TestCase):
    def tearDown(self):
        get_supabase.cache_clear()

    def test_cliente_sdk_y_opciones(self):
        sdk = ModuleType("supabase")
        sdk.create_client = Mock(return_value=object())
        modulo = ModuleType("supabase.client")
        modulo.ClientOptions = Mock(return_value=object())
        with patch.dict("sys.modules", {"supabase": sdk, "supabase.client": modulo}):
            cliente = crear_cliente(Configuracion(**{"supabase_url": VALORES["SUPABASE_URL"], "supabase_service_role_key": VALORES["SUPABASE_SERVICE_ROLE_KEY"]}))
        self.assertIs(cliente, sdk.create_client.return_value)
        self.assertEqual(sdk.create_client.call_args.args, tuple(VALORES.values()))
        self.assertFalse(modulo.ClientOptions.call_args.kwargs["persist_session"])
        self.assertFalse(modulo.ClientOptions.call_args.kwargs["auto_refresh_token"])

    def test_error_sdk_no_expone_secreto(self):
        sdk = ModuleType("supabase")
        sdk.create_client = Mock(side_effect=RuntimeError("sb_secret_sintetica"))
        modulo = ModuleType("supabase.client")
        modulo.ClientOptions = Mock()
        with patch.dict("sys.modules", {"supabase": sdk, "supabase.client": modulo}):
            with self.assertRaises(ErrorConexion) as error:
                crear_cliente(Configuracion("https://demo.supabase.co", "sb_secret_sintetica"))
        self.assertNotIn("sb_secret_sintetica", str(error.exception))

    def test_sdk_ausente(self):
        with patch.dict("sys.modules", {"supabase": None}):
            with self.assertRaisesRegex(ErrorConexion, "Falta el SDK"):
                crear_cliente(Configuracion("https://demo.supabase.co", "sb_secret_sintetica"))

    def test_cliente_reutilizado(self):
        with patch("comun.db.crear_cliente") as crear:
            self.assertIs(get_supabase(), get_supabase())
            crear.assert_called_once_with()

    def test_lectura_limitada_vacia_o_con_datos(self):
        for datos in [[], [{"sector_id": "sintetico"}]]:
            db = Mock()
            db.table.return_value.select.return_value.limit.return_value.execute.return_value = SimpleNamespace(data=datos)
            self.assertEqual(comprobar_conexion(db)["filas_leidas"], len(datos))
            db.table.assert_called_once_with("sectores")
            db.table.return_value.select.assert_called_once_with("sector_id")
            db.table.return_value.select.return_value.limit.assert_called_once_with(1)

    def test_error_red_o_permisos_sin_datos_crudos(self):
        db = Mock()
        db.table.side_effect = RuntimeError("https://privado/?clave=secreto")
        with self.assertRaises(ErrorConexion) as error:
            comprobar_conexion(db)
        self.assertNotIn("secreto", str(error.exception))

    def test_cli_error_controlado(self):
        salida = io.StringIO()
        with patch("comun.db.comprobar_conexion", side_effect=ErrorConfiguracion("Falta SUPABASE_URL")), contextlib.redirect_stdout(salida):
            self.assertEqual(main(), 1)
        self.assertEqual(json.loads(salida.getvalue())["estado"], "error")

    def test_cli_exito(self):
        salida = io.StringIO()
        with patch("comun.db.comprobar_conexion", return_value={"estado": "ok"}), contextlib.redirect_stdout(salida):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(salida.getvalue())["estado"], "ok")


if __name__ == "__main__":
    unittest.main()
