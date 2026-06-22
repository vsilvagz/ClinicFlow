"""Repositorio de usuarios y sus roles.

Gracias a la herencia de tabla única, todos los roles viven en `usuarios`.
Pedir `UsuarioORM` devuelve la subclase correcta (PacienteORM, MedicoORM…)
según la columna discriminadora `rol`; pedir una subclase concreta filtra solo
las filas de ese rol.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.usuarios import MedicoORM, PacienteORM, UsuarioORM
from app.backend.repositories.base import RepositorioBase


class RepositorioUsuarios(RepositorioBase[UsuarioORM]):
    """Acceso a datos de la tabla `usuarios`."""

    def __init__(self, db: Session):
        super().__init__(db, UsuarioORM)

    def obtener_paciente(self, run: int) -> PacienteORM | None:
        """Devuelve el usuario solo si existe y es un paciente."""
        return self.db.get(PacienteORM, run)

    def obtener_medico(self, run: int) -> MedicoORM | None:
        """Devuelve el usuario solo si existe y es un médico."""
        return self.db.get(MedicoORM, run)

    def listar_medicos(self) -> list[MedicoORM]:
        """Lista todos los médicos registrados."""
        return list(self.db.scalars(select(MedicoORM)))
