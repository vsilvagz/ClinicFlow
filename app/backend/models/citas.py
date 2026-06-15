"""Modelo ORM de las citas médicas.

Espejo de persistencia de domain/citas.py. Guarda el estado de cada cita y sus
relaciones: con el paciente y el médico (ambos en la tabla `usuarios`), con la
agenda donde está registrada, y consigo misma para la trazabilidad de los
reagendamientos (una cita reemplaza/es reemplazada por otra).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

# Uuid: tipo de columna para identificadores UUID (nativo en PostgreSQL,
# almacenado como texto en SQLite). DateTime: fecha+hora. Enum: guarda un enum.
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Reutilizamos el enum de estados del dominio como tipo de la columna `estado`.
from app.backend.domain.enums import EstadoCita
from app.backend.core.database import Base

if TYPE_CHECKING:
    from app.backend.models.usuarios import UsuarioORM
    from app.backend.models.agenda import AgendaORM


# ──────────────────────────────────────────────────────────────────────────────
# CitaORM: tabla "citas".
# ──────────────────────────────────────────────────────────────────────────────

class CitaORM(Base):
    __tablename__ = "citas"

    # id: UUID propio de la cita (lo genera el dominio, no la BD).
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)

    # Paciente y médico: ambos son usuarios, por eso las dos FK apuntan a la
    # misma tabla `usuarios`. Al haber dos FK al mismo destino, en las relaciones
    # de abajo hay que indicar explícitamente cuál columna usa cada una.
    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )
    medico_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )

    # especialidad: se guarda como texto (el nombre), igual que en el dominio.
    especialidad: Mapped[str] = mapped_column(String(100), nullable=False)

    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    estado: Mapped[EstadoCita] = mapped_column(SQLEnum(EstadoCita), nullable=False)
    motivo: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Trazabilidad de reagendamientos: dos FK que apuntan a la propia tabla citas.
    # `reagendada_desde_id` = de qué cita viene esta; `reagendada_hacia_id` = por
    # cuál fue reemplazada. Son autorreferencias, por eso usan "citas.id".
    reagendada_desde_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("citas.id"), nullable=True
    )
    reagendada_hacia_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("citas.id"), nullable=True
    )

    # agenda_id: agenda del médico donde queda registrada la cita.
    agenda_id: Mapped[int | None] = mapped_column(
        ForeignKey("agendas.id"), nullable=True
    )

    # Relaciones de navegación. `foreign_keys` resuelve la ambigüedad de tener
    # dos FK (paciente y médico) hacia la tabla usuarios.
    paciente: Mapped["UsuarioORM"] = relationship(foreign_keys=[paciente_id])
    medico: Mapped["UsuarioORM"] = relationship(foreign_keys=[medico_id])
    agenda: Mapped["AgendaORM | None"] = relationship(
        back_populates="citas", foreign_keys=[agenda_id]
    )

    def __repr__(self) -> str:
        return (
            f"CitaORM(id={self.id}, paciente={self.paciente_id}, "
            f"medico={self.medico_id}, estado={self.estado.value})"
        )
