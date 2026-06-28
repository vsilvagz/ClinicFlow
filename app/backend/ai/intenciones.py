"""Contrato de salida estructurada del asistente conversacional.

El modelo de lenguaje no ejecuta acciones ni contiene reglas de negocio: su
único trabajo es traducir el mensaje en lenguaje natural del paciente a una de
estas intenciones, rellenando los parámetros que logre identificar. La
validación, la resolución de identificadores y la ejecución ocurren después en
la capa de servicios, de modo que el sistema sigue siendo correcto aunque el
modelo se equivoque.

El esquema es deliberadamente plano (una sola clase con campos opcionales) en
lugar de una unión discriminada: así es más sencillo de expresar como JSON
Schema para el modelo y más tolerante a respuestas incompletas.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.backend.domain.enums import PrioridadEspera


class AccionAsistente(str, Enum):
    """Acciones que el asistente puede reconocer en un mensaje del paciente."""

    AGENDAR = "agendar"                                # Pedir una hora nueva.
    CANCELAR = "cancelar"                              # Anular una cita existente.
    REAGENDAR = "reagendar"                            # Mover una cita a otra hora.
    CONSULTAR_DISPONIBILIDAD = "consultar_disponibilidad"  # Ver horas libres.
    CONSULTAR_MIS_CITAS = "consultar_mis_citas"        # Listar las citas del paciente.
    INSCRIBIR_ESPERA = "inscribir_espera"              # Entrar a una lista de espera.
    DESCONOCIDA = "desconocida"                        # No se entendió la solicitud.


class IntencionAsistente(BaseModel):
    """Resultado de interpretar un mensaje: la acción y sus parámetros.

    Todos los parámetros son opcionales porque dependen de cuánta información
    haya entregado el paciente; los campos faltantes los completa la
    conversación o los rechaza la validación posterior.
    """

    accion: AccionAsistente = Field(
        description="La acción que el paciente quiere realizar."
    )
    especialidad: str | None = Field(
        default=None,
        description="Especialidad mencionada (p. ej. 'cardiología'), tal como la dijo el paciente.",
    )
    medico: str | None = Field(
        default=None,
        description="Nombre del médico, si el paciente lo indicó.",
    )
    fecha_hora: datetime | None = Field(
        default=None,
        description="Fecha y hora solicitada en formato ISO 8601. Null si no se indicó.",
    )
    nueva_fecha_hora: datetime | None = Field(
        default=None,
        description="Nueva fecha y hora para un reagendamiento, en formato ISO 8601.",
    )
    prioridad: PrioridadEspera | None = Field(
        default=None,
        description="Prioridad declarada para la lista de espera, si corresponde.",
    )
    motivo: str | None = Field(
        default=None,
        description="Motivo de la consulta, si el paciente lo mencionó.",
    )
    respuesta: str = Field(
        default="",
        description="Respuesta breve y en español para el paciente (confirmación o aclaración).",
    )
