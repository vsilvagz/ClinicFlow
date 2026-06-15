"""Modelo ORM de la clínica y sus tablas de asociación.

Espejo de persistencia de la clase de dominio `Clinica` (domain/clinica.py).
Una clínica agrupa médicos y especialidades. Como en el dominio esas colecciones
son listas (un médico puede estar en varias clínicas y una especialidad ofrecerse
en varias), las modelamos con relaciones MUCHOS-A-MUCHOS usando tablas de
asociación intermedias.
"""

from typing import TYPE_CHECKING

# Column / Table: forma de declarar tablas "puras" de asociación (sin clase ORM).
from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.database import Base

if TYPE_CHECKING:
    from app.backend.models.especialidades import EspecialidadORM
    from app.backend.models.usuarios import MedicoORM, RecepcionistaORM


# ──────────────────────────────────────────────────────────────────────────────
# TABLAS DE ASOCIACIÓN (muchos-a-muchos).
# No tienen clase propia: son solo "puentes" con dos claves foráneas. SQLAlchemy
# las usa por debajo cuando recorremos las relaciones `clinica.medicos`, etc.
# ──────────────────────────────────────────────────────────────────────────────

# clinica_medicos: relaciona clínicas con sus médicos.
clinica_medicos = Table(
    "clinica_medicos",
    Base.metadata,
    Column("clinica_rut", ForeignKey("clinicas.rut_empresa"), primary_key=True),
    Column("medico_run", ForeignKey("usuarios.run_usuario"), primary_key=True),
)

# clinica_especialidades: relaciona clínicas con las especialidades que ofrecen.
clinica_especialidades = Table(
    "clinica_especialidades",
    Base.metadata,
    Column("clinica_rut", ForeignKey("clinicas.rut_empresa"), primary_key=True),
    Column("especialidad_id", ForeignKey("especialidades.id"), primary_key=True),
)


# ──────────────────────────────────────────────────────────────────────────────
# ClinicaORM: tabla "clinicas".
# ──────────────────────────────────────────────────────────────────────────────

class ClinicaORM(Base):
    __tablename__ = "clinicas"

    # rut_empresa: clave primaria. Usamos texto porque un RUT lleva puntos y
    # dígito verificador (ej. "76.123.456-7"); no es un entero "limpio".
    rut_empresa: Mapped[str] = mapped_column(String(20), primary_key=True)

    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str] = mapped_column(
        String(250), default="Dirección no especificada", nullable=False
    )

    # medicos / especialidades: los dos lados muchos-a-muchos. `secondary` indica
    # la tabla puente; `back_populates` enlaza con la relación del otro modelo.
    medicos: Mapped[list["MedicoORM"]] = relationship(
        secondary=clinica_medicos, back_populates="clinicas"
    )
    especialidades: Mapped[list["EspecialidadORM"]] = relationship(
        secondary=clinica_especialidades, back_populates="clinicas"
    )

    # recepcionistas: uno-a-muchos. Cada recepcionista tiene su FK `clinica_rut`.
    recepcionistas: Mapped[list["RecepcionistaORM"]] = relationship(
        back_populates="clinica"
    )

    def __repr__(self) -> str:
        return f"ClinicaORM(rut={self.rut_empresa!r}, nombre={self.nombre!r})"
