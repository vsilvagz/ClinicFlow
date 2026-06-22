"""Esquemas Pydantic (DTOs) de las citas médicas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.backend.domain.enums import EstadoCita


class CitaCrear(BaseModel):
    """Datos para solicitar una cita nueva.

    La duración no la fija el cliente libremente: se valida que sea positiva.
    El estado inicial y la hora de fin los calcula el dominio (`Cita.crear`).
    """

    paciente_id: int = Field(gt=0)
    medico_id: int = Field(gt=0)
    inicio: datetime
    duracion_minutos: int = Field(default=30, gt=0, le=480)
    motivo: str = Field(default="", max_length=300)


class CitaReagendar(BaseModel):
    """Nueva hora a la que se mueve una cita existente."""

    nueva_inicio: datetime
    duracion_minutos: int = Field(default=30, gt=0, le=480)


class CitaLeer(BaseModel):
    """Vista pública de una cita."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paciente_id: int
    medico_id: int
    especialidad: str
    inicio: datetime
    fin: datetime
    estado: EstadoCita
    motivo: str
    creada_en: datetime
