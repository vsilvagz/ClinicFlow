"""Repositorio de citas médicas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.domain.citas import ESTADOS_ACTIVOS
from app.backend.models.citas import CitaORM
from app.backend.repositories.base import RepositorioBase


class RepositorioCitas(RepositorioBase[CitaORM]):
    """Acceso a datos de la tabla `citas`."""

    def __init__(self, db: Session):
        super().__init__(db, CitaORM)

    def listar_de_paciente(self, paciente_id: int) -> list[CitaORM]:
        """Todas las citas (historial) de un paciente."""
        return list(
            self.db.scalars(
                select(CitaORM).where(CitaORM.paciente_id == paciente_id)
            )
        )

    def listar_activas_de_medico(self, medico_id: int) -> list[CitaORM]:
        """Citas vigentes (pendientes o confirmadas) de un médico.

        Son las únicas que pueden generar conflictos de agenda, así que el
        servicio las usa para validar solapamientos antes de crear una cita.
        """
        return list(
            self.db.scalars(
                select(CitaORM).where(
                    CitaORM.medico_id == medico_id,
                    CitaORM.estado.in_(ESTADOS_ACTIVOS),
                )
            )
        )
