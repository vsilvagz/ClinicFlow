"""Modelos ORM de la lista de espera.

Espejo de persistencia de domain/lista_espera.py. En el dominio, una lista de
espera pertenece a una especialidad y una clínica, y contiene una colección de
inscripciones, cada una con (paciente, fecha de inscripción, prioridad).

Modelamos eso con DOS tablas:
- `listas_espera`: la lista en sí (especialidad + clínica).
- `inscripciones_espera`: cada paciente inscrito (tabla hija, uno-a-muchos).

Separarlo en dos tablas es la forma relacional natural de guardar una lista de
elementos: cada inscripción es una fila propia con su fecha y prioridad.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.domain.enums import PrioridadEspera
from app.backend.core.database import Base

if TYPE_CHECKING:
    from app.backend.models.especialidades import EspecialidadORM
    from app.backend.models.clinica import ClinicaORM
    from app.backend.models.usuarios import PacienteORM


# ──────────────────────────────────────────────────────────────────────────────
# ListaEsperaORM: tabla "listas_espera". Una lista por (especialidad, clínica).
# ──────────────────────────────────────────────────────────────────────────────

class ListaEsperaORM(Base):
    __tablename__ = "listas_espera"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    especialidad_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    clinica_rut: Mapped[str] = mapped_column(
        ForeignKey("clinicas.rut_empresa"), nullable=False
    )

    # Relaciones de solo lectura hacia la especialidad y la clínica (sin vuelta).
    especialidad: Mapped["EspecialidadORM"] = relationship()
    clinica: Mapped["ClinicaORM"] = relationship()

    # inscripciones: la colección de pacientes en espera (tabla hija).
    inscripciones: Mapped[list["InscripcionEsperaORM"]] = relationship(
        back_populates="lista", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"ListaEsperaORM(id={self.id}, especialidad_id={self.especialidad_id})"


# ──────────────────────────────────────────────────────────────────────────────
# InscripcionEsperaORM: tabla "inscripciones_espera". Un paciente en una lista.
# Equivale a cada tupla (paciente, fecha, prioridad) del dominio.
# ──────────────────────────────────────────────────────────────────────────────

class InscripcionEsperaORM(Base):
    __tablename__ = "inscripciones_espera"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    lista_id: Mapped[int] = mapped_column(
        ForeignKey("listas_espera.id"), nullable=False
    )
    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )

    fecha_inscripcion: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    prioridad: Mapped[PrioridadEspera] = mapped_column(
        SQLEnum(PrioridadEspera), default=PrioridadEspera.NORMAL, nullable=False
    )

    lista: Mapped["ListaEsperaORM"] = relationship(back_populates="inscripciones")
    paciente: Mapped["PacienteORM"] = relationship()

    def __repr__(self) -> str:
        return (
            f"InscripcionEsperaORM(lista={self.lista_id}, "
            f"paciente={self.paciente_id}, prioridad={self.prioridad.value})"
        )
