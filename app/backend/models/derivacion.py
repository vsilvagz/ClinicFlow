"""Modelo ORM de las derivaciones médicas.

Espejo de persistencia de domain/derivacion.py. Una derivación vincula a un
paciente con el médico que la emite, una especialidad destino y, opcionalmente,
un médico destino y la cita que resultó de ella.

Esta tabla tiene tres FK hacia `usuarios` (paciente, médico origen, médico
destino). Como por ahora no necesitamos navegar esas relaciones desde Python,
las dejamos como columnas FK (que ya crean la relación a nivel de base de datos)
sin declarar `relationship()`; se pueden agregar más adelante si hace falta.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.domain.enums import EstadoDerivacion
from app.backend.core.database import Base


# ──────────────────────────────────────────────────────────────────────────────
# DerivacionORM: tabla "derivaciones".
# ──────────────────────────────────────────────────────────────────────────────

class DerivacionORM(Base):
    __tablename__ = "derivaciones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)

    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )
    medico_origen_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )

    especialidad_destino: Mapped[str] = mapped_column(String(100), nullable=False)
    motivo: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    estado: Mapped[EstadoDerivacion] = mapped_column(
        SQLEnum(EstadoDerivacion), nullable=False
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Opcionales: médico destino específico y cita que resultó de la derivación.
    medico_destino_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=True
    )
    cita_resultante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("citas.id"), nullable=True
    )
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return (
            f"DerivacionORM(id={self.id}, paciente={self.paciente_id}, "
            f"destino={self.especialidad_destino!r}, estado={self.estado.value})"
        )
