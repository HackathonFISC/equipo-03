"""Límite de mensajes por persona y en total, para un bot abierto a cualquier usuario.

Cada reporte que pasa el límite llega a la API y después a la Ingesta (que usa el modelo, con cuota).
Sin este límite, una sola persona podría gastar la cuota o llenar la bandeja con mensajes repetidos.
Todo vive en memoria: al reiniciar el bot, los contadores empiezan de cero.
"""
import time
from collections import deque

PERMITIDO = "permitido"
AVISO_USUARIO = "aviso_usuario"  # Pasó su propio límite: se le avisa una vez por ventana.
AVISO_GLOBAL = "aviso_global"    # El bot está saturado: se avisa una vez por ventana a cada persona.
SILENCIO = "silencio"            # Ya se le avisó en esta ventana: se ignora sin responder.

POR_USUARIO = 8
EN_TOTAL = 120
VENTANA_SEGUNDOS = 600.0
MAX_PERSONAS_EN_MEMORIA = 5000


class LimiteMensajes:
    def __init__(self, por_usuario=POR_USUARIO, en_total=EN_TOTAL, ventana=VENTANA_SEGUNDOS, reloj=time.monotonic):
        self.por_usuario, self.en_total, self.ventana, self._reloj = por_usuario, en_total, ventana, reloj
        self._usuarios: dict[int, deque[float]] = {}
        self._total: deque[float] = deque()
        self._avisados: dict[int, float] = {}

    def _podar(self, eventos: deque[float], ahora: float) -> None:
        while eventos and ahora - eventos[0] >= self.ventana:
            eventos.popleft()

    def _limpiar(self, ahora: float) -> None:
        """Evita que la memoria crezca sin tope con muchas personas distintas."""
        if len(self._usuarios) <= MAX_PERSONAS_EN_MEMORIA:
            return
        for clave in list(self._usuarios):
            self._podar(self._usuarios[clave], ahora)
            if not self._usuarios[clave]:
                del self._usuarios[clave]
        for clave in [k for k, t in self._avisados.items() if ahora - t >= self.ventana]:
            del self._avisados[clave]

    def evaluar(self, usuario_id: int) -> str:
        """Cuenta el mensaje si cabe en los límites; si no, dice si hay que avisar o callar."""
        ahora = self._reloj()
        self._limpiar(ahora)
        propios = self._usuarios.setdefault(usuario_id, deque())
        self._podar(propios, ahora)
        self._podar(self._total, ahora)
        motivo = None
        if len(propios) >= self.por_usuario:
            motivo = AVISO_USUARIO
        elif len(self._total) >= self.en_total:
            motivo = AVISO_GLOBAL
        if motivo is None:
            propios.append(ahora)
            self._total.append(ahora)
            return PERMITIDO
        # El intento rechazado no se cuenta: pasada la ventana, la persona vuelve a poder escribir.
        ultimo_aviso = self._avisados.get(usuario_id)
        if ultimo_aviso is not None and ahora - ultimo_aviso < self.ventana:
            return SILENCIO
        self._avisados[usuario_id] = ahora
        return motivo
