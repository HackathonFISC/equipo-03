"""Fronteras HTTP reales en memoria; Auth, BD y Telegram son dobles explícitos.

No acredita el caso 19 en Supabase, idempotencia persistida ni envío real.
"""
import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import UUID

from fastapi.testclient import TestClient
import httpx
from postgrest.exceptions import APIError
import pytest
from telegram.error import Forbidden, TimedOut

from api.auth import obtener_verificador
from api.dependencias import obtener_db, secreto_configurado
from api.main import app
from bot.bandeja import enviar_uno

USUARIO = UUID('79e1e74e-9ba6-5b4d-8e88-dc54b275f822')
PLAN = '2cde597b-af8d-50cc-ac4c-e28b31bc3108'
CUERPO = dict(datos_version='ensayo-v5-1', politica_version='ensayo-politica-1',
              motivo='Caso sintético independiente', bloqueos_reconocidos=[])


@pytest.fixture
def frontera():
    anteriores = app.dependency_overrides.copy()
    db = Mock()
    verificador = Mock()
    verificador.usuario_id.return_value = USUARIO
    app.dependency_overrides[obtener_db] = lambda: db
    app.dependency_overrides[obtener_verificador] = lambda: verificador
    app.dependency_overrides[secreto_configurado] = lambda: 'secreto-sintetico-v5-012345'
    try:
        yield db, verificador
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)


@pytest.mark.parametrize('fila', [None, {'rol': 'conductor', 'activo': True},
    {'rol': 'coordinador', 'activo': False}, {'rol': 'coordinador', 'activo': 'true'}])
@pytest.mark.parametrize('accion', ['aprobar', 'rechazar'])
def test_c19_sesion_valida_y_rol_declarado_no_bastan(frontera, fila, accion):
    db, verificador = frontera
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [fila] if fila else []
    cuerpo = CUERPO if accion == 'aprobar' else {'motivo': 'Rechazo sintético'}
    with TestClient(app) as cliente:
        r = cliente.post(f'/planes/{PLAN}/versiones/1/{accion}', json=cuerpo,
            headers={'Authorization': 'Bearer v5.sesion.ficticia', 'X-Rol': 'coordinador', 'X-Usuario-Id': PLAN})
    assert r.status_code == 403 and r.json()['codigo'] == 'sin_permiso'
    db.rpc.assert_not_called()
    verificador.usuario_id.assert_called_once_with('v5.sesion.ficticia')
    db.table.return_value.select.return_value.eq.assert_called_once_with('usuario_id', str(USUARIO))


def test_control_positivo_usa_identidad_verificada_y_no_encabezado(frontera):
    db, _ = frontera
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [dict(rol='coordinador', activo=True)]
    db.rpc.return_value.execute.return_value.data = dict(plan_id=PLAN, version=1, estado='aprobado',
        aprobacion_id='3796f4ea-de86-5118-93ca-8ad1b680c088', repetido=False)
    with TestClient(app) as cliente:
        r = cliente.post(f'/planes/{PLAN}/versiones/1/aprobar', json=CUERPO,
            headers={'Authorization': 'Bearer v5.sesion.ficticia', 'X-Usuario-Id': PLAN})
    assert r.status_code == 200
    nombre, parametros = db.rpc.call_args.args
    assert nombre == 'ra_aprobar_plan' and parametros['p_usuario_id'] == str(USUARIO)


@pytest.mark.parametrize('fallo,estado', [(TimedOut('detalle-privado'), 'incierto'),
                                        (Forbidden('detalle-privado'), 'fallido')])
def test_c23_fallo_proveedor_cruza_bot_api_sin_reenvio(frontera, fallo, estado):
    db, _ = frontera
    bot = Mock()
    bot.send_message = AsyncMock(side_effect=fallo)
    aviso = dict(aviso_id=PLAN, chat_id=-1001, tipo='distribucion', version=1,
        punto_nombre='ENSAYO SINTETICO', litros_asignados=1000,
        ventana_inicio='2026-10-17T08:00:00-05:00', ventana_fin='2026-10-17T08:10:00-05:00')
    async def ejecutar():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://ensayo',
                headers={'X-Secreto-Bot': 'secreto-sintetico-v5-012345'}) as cliente:
            await enviar_uno(bot, cliente, 'trabajador-sintetico', aviso)
    asyncio.run(ejecutar())
    bot.send_message.assert_awaited_once()
    db.rpc.assert_called_once()
    _, parametros = db.rpc.call_args.args
    assert parametros['p_estado'] == estado and parametros['p_proveedor_mensaje_id'] is None
    assert 'detalle-privado' not in parametros['p_error']


def test_c23_acuse_incierto_no_repite_envio(frontera):
    db, _ = frontera
    db.rpc.return_value.execute.side_effect = APIError({'code': '08006', 'message': 'detalle-privado'})
    bot = Mock()
    bot.send_message = AsyncMock(return_value=Mock(message_id=17))
    aviso = dict(aviso_id=PLAN, chat_id=-1001, tipo='distribucion', version=1,
        punto_nombre='ENSAYO SINTETICO', litros_asignados=1000,
        ventana_inicio='2026-10-17T08:00:00-05:00', ventana_fin='2026-10-17T08:10:00-05:00')
    async def ejecutar():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://ensayo',
                headers={'X-Secreto-Bot': 'secreto-sintetico-v5-012345'}) as cliente:
            await enviar_uno(bot, cliente, 'trabajador-sintetico', aviso)
    asyncio.run(ejecutar())
    bot.send_message.assert_awaited_once()
    db.rpc.assert_called_once()
