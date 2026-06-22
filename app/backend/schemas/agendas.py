"""Esquemas Pydantic (DTOs) de la agenda médica y sus componentes.

La agenda se compone de tres tipos de "reglas de calendario" que el cliente
configura por separado: horarios recurrentes de atención, bloqueos puntuales y
suspensiones de un período. Cada uno tiene su propio esquema de entrada.
"""

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

# ──────────────────────────────────────────────────────────────────────────────
# Agenda.
# ──────────────────────────────────────────────────────────────────────────────

class AgendaCrear(BaseModel):
    """Datos para crear la agenda de un médico."""

    medico_run: int = Field(gt=0)
    duracion_slot_minutos: int = Field(default=30, gt=0, le=480)
    capacidad_maxima_dia: int | None = Field(default=None, gt=0)


class AgendaLeer(BaseModel):
    """Vista pública de una agenda."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    medico_run: int
    duracion_slot_minutos: int
    capacidad_maxima_dia: int | None


# ──────────────────────────────────────────────────────────────────────────────
# Horarios recurrentes (franja semanal de atención).
# ──────────────────────────────────────────────────────────────────────────────

class BloqueHorarioCrear(BaseModel):
    """Franja semanal recurrente: día (0=lunes … 6=domingo) y horas."""

    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fin: time


class BloqueHorarioLeer(BloqueHorarioCrear):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ──────────────────────────────────────────────────────────────────────────────
# Bloqueos y suspensiones (intervalos concretos de fecha+hora).
# ──────────────────────────────────────────────────────────────────────────────

class BloqueoCrear(BaseModel):
    """Bloqueo puntual de un intervalo (no cancela citas existentes)."""

    inicio: datetime
    fin: datetime
    motivo: str = Field(default="", max_length=300)


class SuspensionCrear(BaseModel):
    """Suspensión completa de la agenda en un período (cancela citas activas)."""

    inicio: datetime
    fin: datetime
    motivo: str = Field(default="", max_length=300)


# ──────────────────────────────────────────────────────────────────────────────
# Consulta de disponibilidad.
# ──────────────────────────────────────────────────────────────────────────────

class DisponibilidadConsulta(BaseModel):
    """Pregunta si un horario puntual está disponible en la agenda."""

    inicio: datetime
    duracion_minutos: int | None = Field(default=None, gt=0, le=480)
