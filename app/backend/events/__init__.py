"""Bus de eventos del dominio para automatizaciones desacopladas.

Permite que una acción (por ejemplo, cancelar una cita) dispare automatizaciones
(por ejemplo, ofrecer el cupo liberado a la lista de espera) SIN que el servicio
que la origina conozca a los que reaccionan. Quien produce el hecho solo lo
`emitir()`; cada servicio interesado se `suscribir()` por el nombre del evento.

Es deliberadamente mínimo —síncrono y en memoria— porque para las
automatizaciones de ClinicFlow es suficiente, y así es fácil de razonar y de
testear. La regla clave: un fallo en una automatización NO debe tumbar la acción
principal que la disparó, por eso `emitir()` aísla cada handler.
"""

from collections import defaultdict
from typing import Callable

# Nombres de los eventos del dominio (constantes para no repartir strings sueltos).
CITA_CANCELADA = "cita_cancelada"

# Registro interno: nombre de evento → lista de handlers suscritos.
_suscriptores: dict[str, list[Callable]] = defaultdict(list)


def suscribir(evento: str, handler: Callable) -> None:
    """Registra un handler que se ejecutará cada vez que se emita `evento`."""
    if handler not in _suscriptores[evento]:
        _suscriptores[evento].append(handler)


def emitir(evento: str, **datos) -> None:
    """Ejecuta, en orden, todos los handlers suscritos a `evento`.

    Cada handler se aísla: si uno falla, se ignora su error para que la
    operación que originó el evento (p. ej. la cancelación de la cita) siga
    siendo correcta. Las automatizaciones son "best effort".
    """
    for handler in list(_suscriptores[evento]):
        try:
            handler(**datos)
        except Exception:  # noqa: BLE001 — una automatización no debe romper la acción base.
            pass
