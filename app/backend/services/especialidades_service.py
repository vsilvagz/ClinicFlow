"""Casos de uso sobre especialidades médicas.

La capa de servicios orquesta repositorios y reglas de negocio. Aquí es simple
(CRUD con una validación de unicidad), pero mantiene el patrón: la API no habla
directamente con la base de datos, sino con estos casos de uso.
"""

from sqlalchemy.orm import Session

from app.backend.models.especialidades import EspecialidadORM
from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.schemas.especialidades import EspecialidadCrear


class EspecialidadYaExiste(Exception):
    """Ya hay una especialidad registrada con ese nombre."""


def crear_especialidad(db: Session, datos: EspecialidadCrear) -> EspecialidadORM:
    """Crea una especialidad, rechazando nombres duplicados."""
    repo = RepositorioEspecialidades(db)
    if repo.obtener_por_nombre(datos.nombre) is not None:
        raise EspecialidadYaExiste(
            f"Ya existe una especialidad llamada '{datos.nombre}'."
        )

    especialidad = EspecialidadORM(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
    )
    repo.agregar(especialidad)
    db.commit()
    db.refresh(especialidad)
    return especialidad


def listar_especialidades(db: Session) -> list[EspecialidadORM]:
    """Devuelve todas las especialidades registradas."""
    return RepositorioEspecialidades(db).listar()


def obtener_especialidad(db: Session, especialidad_id: int) -> EspecialidadORM | None:
    """Devuelve la especialidad con ese id, o None si no existe."""
    return RepositorioEspecialidades(db).obtener(especialidad_id)
