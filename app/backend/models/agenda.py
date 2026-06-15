"""Modelos ORM de la agenda médica y sus componentes.

Espejo de persistencia de domain/agenda.py. La `Agenda` del dominio contiene
cuatro colecciones: horarios recurrentes, bloqueos puntuales, suspensiones y
citas. Cada una de esas colecciones se modela como una TABLA HIJA con una FK
de vuelta a la agenda a la que pertenece (relación uno-a-muchos).

La agenda, a su vez, pertenece a UN médico (uno-a-uno, por composición).
"""

from datetime import datetime, time
from typing import TYPE_CHECKING

# DateTime: columna de fecha+hora. Time: columna de solo hora (ej. 09:00).
from sqlalchemy import DateTime, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.database import Base

if TYPE_CHECKING:
    from app.backend.models.usuarios import MedicoORM
    from app.backend.models.citas import CitaORM


# ──────────────────────────────────────────────────────────────────────────────
# AgendaORM: tabla "agendas". Una por médico.
# ──────────────────────────────────────────────────────────────────────────────

class AgendaORM(Base):
    __tablename__ = "agendas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # medico_run: FK al dueño de la agenda. `unique=True` impone el uno-a-uno:
    # no puede haber dos agendas para el mismo médico.
    medico_run: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), unique=True, nullable=False
    )

    # Configuración de la agenda (mismos parámetros que el dominio).
    duracion_slot_minutos: Mapped[int] = mapped_column(default=30, nullable=False)
    capacidad_maxima_dia: Mapped[int | None] = mapped_column(nullable=True)

    # medico: lado uno-a-uno. Apunta de vuelta a MedicoORM.agenda.
    medico: Mapped["MedicoORM"] = relationship(back_populates="agenda")

    # Colecciones hijas. cascade="all, delete-orphan": si se borra la agenda o se
    # quita un elemento de la lista, su fila hija también se elimina.
    horarios: Mapped[list["BloqueHorarioORM"]] = relationship(
        back_populates="agenda", cascade="all, delete-orphan"
    )
    bloqueos: Mapped[list["BloqueoORM"]] = relationship(
        back_populates="agenda", cascade="all, delete-orphan"
    )
    suspensiones: Mapped[list["SuspensionORM"]] = relationship(
        back_populates="agenda", cascade="all, delete-orphan"
    )
    # Las citas NO se borran con la agenda (son historial clínico): sin cascade.
    citas: Mapped[list["CitaORM"]] = relationship(back_populates="agenda")

    def __repr__(self) -> str:
        return f"AgendaORM(id={self.id}, medico_run={self.medico_run})"


# ──────────────────────────────────────────────────────────────────────────────
# BloqueHorarioORM: franja semanal recurrente (ej. "lunes 09:00–13:00").
# ──────────────────────────────────────────────────────────────────────────────

class BloqueHorarioORM(Base):
    __tablename__ = "bloques_horario"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agenda_id: Mapped[int] = mapped_column(ForeignKey("agendas.id"), nullable=False)

    dia_semana: Mapped[int] = mapped_column(nullable=False)  # 0=lunes … 6=domingo.
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)

    agenda: Mapped["AgendaORM"] = relationship(back_populates="horarios")


# ──────────────────────────────────────────────────────────────────────────────
# BloqueoORM: bloqueo puntual de un intervalo (no cancela citas existentes).
# ──────────────────────────────────────────────────────────────────────────────

class BloqueoORM(Base):
    __tablename__ = "bloqueos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agenda_id: Mapped[int] = mapped_column(ForeignKey("agendas.id"), nullable=False)

    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    motivo: Mapped[str] = mapped_column(String(300), default="", nullable=False)

    agenda: Mapped["AgendaORM"] = relationship(back_populates="bloqueos")


# ──────────────────────────────────────────────────────────────────────────────
# SuspensionORM: suspensión completa de la agenda en un período.
# ──────────────────────────────────────────────────────────────────────────────

class SuspensionORM(Base):
    __tablename__ = "suspensiones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agenda_id: Mapped[int] = mapped_column(ForeignKey("agendas.id"), nullable=False)

    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    motivo: Mapped[str] = mapped_column(String(300), default="", nullable=False)

    agenda: Mapped["AgendaORM"] = relationship(back_populates="suspensiones")
