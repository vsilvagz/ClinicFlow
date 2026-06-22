"""Esquemas Pydantic (DTOs) de la lista de espera."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.backend.domain.enums import PrioridadEspera


class ListaEsperaCrear(BaseModel):
    """Datos para abrir (o ubicar) la lista de espera de una especialidad en una clínica."""

    especialidad_id: int = Field(gt=0)
    clinica_rut: str = Field(min_length=1, max_length=20)


class ListaEsperaLeer(BaseModel):
    """Vista pública de una lista de espera."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    especialidad_id: int
    clinica_rut: str


class InscripcionCrear(BaseModel):
    """Datos para inscribir a un paciente en una lista de espera."""

    paciente_id: int = Field(gt=0)
    prioridad: PrioridadEspera = PrioridadEspera.NORMAL


class InscripcionLeer(BaseModel):
    """Vista pública de una inscripción en lista de espera."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lista_id: int
    paciente_id: int
    fecha_inscripcion: datetime
    prioridad: PrioridadEspera
