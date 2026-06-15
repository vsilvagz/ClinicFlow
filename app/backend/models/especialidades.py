"""Modelo ORM de las especialidades médicas.

Este es el "espejo" de persistencia de la clase de dominio `Especialidad`
(ver `domain/especialidades.py`). NO es la misma clase: el dominio guarda la
lógica y las reglas; este modelo solo describe la TABLA `especialidades` y cómo
se guardan/leen sus filas. El paso 4 (repositorios) traducirá entre ambos.

Le ponemos el sufijo `ORM` para no confundirlo con la clase de dominio.
"""

# String: tipo de columna de texto con longitud máxima.
from sqlalchemy import String

# Mapped / mapped_column: estilo moderno (SQLAlchemy 2.0) para declarar columnas
# con su tipo de Python. relationship: define una relación entre tablas.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# TYPE_CHECKING evita un import circular: solo se evalúa al revisar tipos, no en
# ejecución. Lo usamos para anotar la relación con UsuarioORM/MedicoORM sin
# importar usuarios.py de verdad (que a su vez importa este archivo).
from typing import TYPE_CHECKING

# Base declarativa: todas las tablas heredan de ella (definida en core/database.py).
from app.backend.core.database import Base

if TYPE_CHECKING:
    from app.backend.models.usuarios import MedicoORM
    from app.backend.models.clinica import ClinicaORM


# ──────────────────────────────────────────────────────────────────────────────
# EspecialidadORM: tabla "especialidades".
# El administrador puede crear/editar especialidades, por eso es una tabla propia
# (entidad) y no un simple texto repetido en cada médico.
# ──────────────────────────────────────────────────────────────────────────────

class EspecialidadORM(Base):
    __tablename__ = "especialidades"

    # id: clave primaria autoincremental (surrogate key). Aunque el dominio
    # compara especialidades por nombre, en la BD usamos un id entero para que
    # las claves foráneas (FK) desde otras tablas sean simples y eficientes.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # nombre: único, porque no debe haber dos especialidades con el mismo nombre.
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # descripcion: opcional; por defecto vacía (igual que en el dominio).
    descripcion: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    # medicos: lado "uno-a-muchos" de la relación. Una especialidad puede tener
    # muchos médicos; cada médico apunta de vuelta con `especialidad`.
    # Es perezosa: no carga los médicos hasta que se acceden.
    medicos: Mapped[list["MedicoORM"]] = relationship(back_populates="especialidad")

    # clinicas: lado "muchos-a-muchos" con ClinicaORM, a través de la tabla
    # intermedia "clinica_especialidades" (definida en clinica.py). Una
    # especialidad puede ofrecerse en varias clínicas y viceversa.
    clinicas: Mapped[list["ClinicaORM"]] = relationship(
        secondary="clinica_especialidades", back_populates="especialidades"
    )

    def __repr__(self) -> str:
        return f"EspecialidadORM(id={self.id}, nombre={self.nombre!r})"
