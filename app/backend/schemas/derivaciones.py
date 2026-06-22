"""Esquemas Pydantic (DTOs) de las derivaciones médicas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.backend.domain.enums import EstadoDerivacion


class DerivacionCrear(BaseModel):
    """Datos con los que un médico emite una derivación.

    El estado inicial (PENDIENTE) y la fecha de expiración los calcula el
    dominio (`Derivacion.crear`) a partir de `dias_vigencia`.
    """

    paciente_id: int = Field(gt=0)
    medico_origen_id: int = Field(gt=0)
    especialidad_destino: str = Field(min_length=1, max_length=100)
    motivo: str = Field(default="", max_length=300)
    dias_vigencia: int = Field(default=30, gt=0, le=365)
    medico_destino_id: int | None = Field(default=None, gt=0)
    notas: str | None = Field(default=None, max_length=500)


class DerivacionCompletar(BaseModel):
    """Cita con la que el paciente concretó la derivación."""

    cita_id: UUID


class DerivacionLeer(BaseModel):
    """Vista pública de una derivación."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paciente_id: int
    medico_origen_id: int
    especialidad_destino: str
    motivo: str
    estado: EstadoDerivacion
    creada_en: datetime
    expira_en: datetime
    medico_destino_id: int | None
    cita_resultante_id: UUID | None
    notas: str | None
