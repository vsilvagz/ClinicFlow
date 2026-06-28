"""Repositorio de derivaciones médicas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.domain.enums import EstadoDerivacion
from app.backend.models.derivacion import DerivacionORM
from app.backend.repositories.base import RepositorioBase


class RepositorioDerivaciones(RepositorioBase[DerivacionORM]):
    """Acceso a datos de la tabla `derivaciones`."""

    def __init__(self, db: Session):
        super().__init__(db, DerivacionORM)

    def listar_de_paciente(self, paciente_id: int) -> list[DerivacionORM]:
        """Todas las derivaciones (historial) de un paciente."""
        return list(
            self.db.scalars(
                select(DerivacionORM).where(DerivacionORM.paciente_id == paciente_id)
            )
        )

    def listar_pendientes_de_paciente(self, paciente_id: int) -> list[DerivacionORM]:
        """Derivaciones aún sin concretar de un paciente."""
        return list(
            self.db.scalars(
                select(DerivacionORM).where(
                    DerivacionORM.paciente_id == paciente_id,
                    DerivacionORM.estado == EstadoDerivacion.PENDIENTE,
                )
            )
        )

    def listar_pendientes_de_medico(self, medico_id: int) -> list[DerivacionORM]:
        """Derivaciones aún sin concretar emitidas por un médico."""
        return list(
            self.db.scalars(
                select(DerivacionORM).where(
                    DerivacionORM.medico_origen_id == medico_id,
                    DerivacionORM.estado == EstadoDerivacion.PENDIENTE,
                )
            )
        )

    def listar_pendientes(self) -> list[DerivacionORM]:
        """Todas las derivaciones pendientes (para el barrido de expiración)."""
        return list(
            self.db.scalars(
                select(DerivacionORM).where(
                    DerivacionORM.estado == EstadoDerivacion.PENDIENTE
                )
            )
        )
