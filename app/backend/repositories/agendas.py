"""Repositorio de agendas médicas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.agenda import AgendaORM
from app.backend.repositories.base import RepositorioBase


class RepositorioAgendas(RepositorioBase[AgendaORM]):
    """Acceso a datos de la tabla `agendas`."""

    def __init__(self, db: Session):
        super().__init__(db, AgendaORM)

    def obtener_por_medico(self, medico_run: int) -> AgendaORM | None:
        """Devuelve la agenda del médico (relación uno-a-uno), o None si no tiene."""
        return self.db.scalar(
            select(AgendaORM).where(AgendaORM.medico_run == medico_run)
        )
