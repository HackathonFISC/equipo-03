"""Arranque del trabajador con la API; sin conexiones durante la importación."""
import asyncio
from contextlib import asynccontextmanager
import errno
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
logger = logging.getLogger('rutaagua.agentes')


def automatico():
    valores = {**dotenv_values(RAIZ/'.env', interpolate=False), **os.environ}
    valor = (valores.get('TRABAJADOR_AUTOMATICO') or 'true').strip().lower()
    if valor not in {'true', 'false', '1', '0'}:
        raise ValueError('TRABAJADOR_AUTOMATICO debe ser true o false')
    return valor in {'true', '1'}


class ServicioAgentes:
    """Un hijo administrado por checkout, incluso con varias instancias de API.

    Las reservas de la BD siguen siendo la protección de cada ejecución.
    El bloqueo local evita lanzar hijos extra durante el arranque de la API.
    """
    def __init__(self, raiz=RAIZ):
        self.raiz = Path(raiz)
        self.proceso = None
        self.bloqueo = None
        self.temporal = None
        self.parada = None
        self.estado = 'detenido'

    def _reservar(self):
        carpeta = self.raiz/'.runtime'
        carpeta.mkdir(exist_ok=True)
        self.bloqueo = (carpeta/'agentes.lock').open('a+b')
        if self.bloqueo.seek(0, 2) == 0:
            self.bloqueo.write(b'0')
            self.bloqueo.flush()
        self.bloqueo.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.bloqueo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.bloqueo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.bloqueo.close()
            self.bloqueo = None
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            return False
        return True

    def iniciar(self):
        if self.proceso is not None:
            return
        if not self._reservar():
            self.estado = 'otra_instancia'
            logger.info('Otra instancia de esta API administra el trabajador de agentes.')
            return
        try:
            self.temporal = tempfile.TemporaryDirectory(prefix='rutaagua-agentes-')
            self.parada = Path(self.temporal.name)/'detener'
            opciones = dict(cwd=str(self.raiz), stdin=subprocess.DEVNULL)
            if os.name == 'nt':
                opciones['creationflags'] = subprocess.CREATE_NO_WINDOW
            self.proceso = subprocess.Popen([sys.executable, '-u', '-m',
                'orquestador.trabajador', '--archivo-parada', str(self.parada)], **opciones)
            self.estado = 'iniciado'
            logger.info('Trabajador de agentes iniciado automáticamente con la API.')
        except Exception:
            self.cerrar()
            raise

    def consultar(self):
        if self.proceso is not None and self.proceso.poll() is not None:
            self.estado = 'fallido' if self.proceso.returncode else 'finalizado'
        return self.estado

    def cerrar(self):
        try:
            if self.proceso is not None and self.proceso.poll() is None:
                self.parada.touch()
                try:
                    # Dejar terminar la etapa actual antes de salir.
                    self.proceso.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    logger.warning('El trabajador no terminó a tiempo; su reserva pendiente requiere revisión.')
                    self.proceso.terminate()
                    try:
                        self.proceso.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.proceso.kill()
                        self.proceso.wait(timeout=5)
        finally:
            # Si no se confirmó el cierre, conservar recursos y bloqueo.
            if self.proceso is None or self.proceso.poll() is not None:
                self.proceso = None
                if self.temporal is not None:
                    self.temporal.cleanup()
                    self.temporal = None
                if self.bloqueo is not None:
                    self.bloqueo.close()
                    self.bloqueo = None
                self.estado = 'detenido'


@asynccontextmanager
async def ciclo_vida_agentes(app):
    servicio = ServicioAgentes()
    app.state.servicio_agentes = servicio
    monitor = None

    async def observar():
        while True:
            await asyncio.sleep(2)
            if servicio.consultar() in {'fallido', 'finalizado'}:
                logger.error('El trabajador se detuvo. Revisar configuración y migraciones; no se reinicia a ciegas.')
                return

    try:
        if automatico():
            servicio.iniciar()
            if servicio.estado == 'iniciado':
                monitor = asyncio.create_task(observar())
        else:
            servicio.estado = 'desactivado'
            logger.info('Trabajador automático desactivado por configuración explícita.')
        yield
    finally:
        if monitor is not None:
            monitor.cancel()
            try:
                await monitor
            except asyncio.CancelledError:
                pass
        await asyncio.to_thread(servicio.cerrar)
