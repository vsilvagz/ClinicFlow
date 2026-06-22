"""Esquemas Pydantic (DTOs) de las clínicas."""

from pydantic import BaseModel, ConfigDict, Field


class ClinicaCrear(BaseModel):
    """Datos para registrar una clínica nueva."""

    # El RUT lleva puntos y dígito verificador, por eso es texto (no entero).
    rut_empresa: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=150)
    direccion: str = Field(default="Dirección no especificada", max_length=250)


class ClinicaLeer(BaseModel):
    """Vista pública de una clínica."""

    model_config = ConfigDict(from_attributes=True)

    rut_empresa: str
    nombre: str
    direccion: str
