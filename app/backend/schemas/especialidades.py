"""Esquemas Pydantic (DTOs) de las especialidades médicas.

Los esquemas son el "contrato" de la API: definen qué JSON se acepta en las
peticiones (entrada) y qué JSON se devuelve en las respuestas (salida). Son una
capa distinta de los modelos ORM y de las clases de dominio:

- ORM     → cómo se guarda en la base de datos.
- Dominio → las reglas de negocio.
- Schema  → cómo se ve la información "por fuera" (en HTTP/JSON).

Separarlos evita filtrar detalles internos y permite validar la entrada antes de
que llegue a la lógica.
"""

from pydantic import BaseModel, ConfigDict, Field


class EspecialidadCrear(BaseModel):
    """Datos que el cliente envía para crear una especialidad."""

    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default="", max_length=500)


class EspecialidadLeer(BaseModel):
    """Datos que la API devuelve de una especialidad."""

    # from_attributes=True permite construir el schema directamente desde un
    # objeto ORM (lee sus atributos), sin convertirlo a dict a mano.
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str
