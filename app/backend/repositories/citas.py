"""Repositorio de citas médicas."""

from datetime import date, datetime, time

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

    def listar_activas_de_paciente_por_especialidad(
        self, paciente_id: int, especialidad: str, desde: datetime, hasta: datetime
    ) -> list[CitaORM]:
        """Citas vigentes de un paciente, de una especialidad, dentro de un rango.

        Sirve para impedir que un paciente acumule varias citas de la misma
        especialidad muy seguidas: el servicio consulta la ventana alrededor de la
        hora pedida antes de crear la cita.
        """
        return list(
            self.db.scalars(
                select(CitaORM).where(
                    CitaORM.paciente_id == paciente_id,
                    CitaORM.especialidad == especialidad,
                    CitaORM.estado.in_(ESTADOS_ACTIVOS),
                    CitaORM.inicio >= desde,
                    CitaORM.inicio <= hasta,
                )
            )
        )

    def listar_del_dia(self, fecha: date) -> list[CitaORM]:
        """Todas las citas de un día (para el dashboard global)."""
        inicio = datetime.combine(fecha, time.min)
        fin = datetime.combine(fecha, time.max)
        return list(
            self.db.scalars(
                select(CitaORM)
                .where(CitaORM.inicio >= inicio, CitaORM.inicio <= fin)
                .order_by(CitaORM.inicio)
            )
        )

    def listar_del_dia_de_medico(self, medico_id: int, fecha: date) -> list[CitaORM]:
        """Citas de un médico en un día específico."""
        inicio = datetime.combine(fecha, time.min)
        fin = datetime.combine(fecha, time.max)
        return list(
            self.db.scalars(
                select(CitaORM)
                .where(
                    CitaORM.medico_id == medico_id,
                    CitaORM.inicio >= inicio,
                    CitaORM.inicio <= fin,
                )
                .order_by(CitaORM.inicio)
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
