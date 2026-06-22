"""Repositorio de especialidades médicas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.especialidades import EspecialidadORM
from app.backend.repositories.base import RepositorioBase


class RepositorioEspecialidades(RepositorioBase[EspecialidadORM]):
    """Acceso a datos de la tabla `especialidades`."""

    def __init__(self, db: Session):
        super().__init__(db, EspecialidadORM)

    def obtener_por_nombre(self, nombre: str) -> EspecialidadORM | None:
        """Busca una especialidad por su nombre (único)."""
        return self.db.scalar(
            select(EspecialidadORM).where(EspecialidadORM.nombre == nombre)
        )
