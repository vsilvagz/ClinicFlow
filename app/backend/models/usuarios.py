"""Modelos ORM de los usuarios del sistema y sus roles.

Espejo de persistencia de las clases de dominio de `domain/usuarios.py`
(Usuario, Paciente, Medico, Recepcionista, Administrador).

Estrategia de mapeo: HERENCIA DE TABLA ÚNICA (single-table inheritance).
Todos los roles comparten UNA sola tabla `usuarios`, con una columna
discriminadora `rol` que indica qué tipo de usuario es cada fila. SQLAlchemy
usa esa columna para devolver la subclase correcta (PacienteORM, MedicoORM…).
Esto refleja la misma jerarquía del dominio con un modelo relacional simple.

Las columnas específicas de un rol (p. ej. `especialidad_id` del médico) viven
en la misma tabla y son NULAS para los roles que no las usan: es la consecuencia
natural de tener una sola tabla para toda la jerarquía.
"""

from typing import TYPE_CHECKING

# BigInteger: entero grande (para teléfonos). Boolean: bandera verdadero/falso.
# Enum SQL: guarda un valor de enum. ForeignKey: clave foránea. String: texto.
# text: literal SQL para el valor por defecto a nivel de base de datos.
from sqlalchemy import BigInteger, Boolean, Enum as SQLEnum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Reutilizamos el MISMO enum del dominio como tipo de la columna `rol`.
from app.backend.domain.enums import RolUsuario
from app.backend.core.database import Base

if TYPE_CHECKING:
    from app.backend.models.especialidades import EspecialidadORM
    from app.backend.models.clinica import ClinicaORM
    from app.backend.models.agenda import AgendaORM


# ──────────────────────────────────────────────────────────────────────────────
# UsuarioORM: tabla "usuarios" y raíz de la jerarquía.
# Contiene los datos comunes a todos los roles. No se instancia directamente;
# siempre se crea una de sus subclases (Paciente, Medico, etc.).
# ──────────────────────────────────────────────────────────────────────────────

class UsuarioORM(Base):
    __tablename__ = "usuarios"

    # run_usuario: clave primaria. Es el RUN de la persona, así que NO es
    # autoincremental: lo provee el sistema, no la base de datos.
    run_usuario: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)

    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    correo: Mapped[str] = mapped_column(String(150), nullable=False)

    # telefono: BigInteger porque un número con código de país no cabe siempre
    # en un entero normal de 32 bits.
    telefono: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # rol: columna discriminadora. Guarda el valor del enum RolUsuario y le dice
    # a SQLAlchemy qué subclase ORM corresponde a cada fila.
    rol: Mapped[RolUsuario] = mapped_column(SQLEnum(RolUsuario), nullable=False)

    # password_hash: hash bcrypt de la contraseña (nunca se guarda en texto plano).
    # Queda vacío para usuarios sin credenciales (p. ej. pacientes que solo reservan).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    # activo: usuarios dados de baja por el administrador no pueden iniciar sesión.
    # server_default asegura el valor en la tabla; default lo aplica al insertar.
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    # __mapper_args__ configura la herencia:
    #   polymorphic_on=rol         → columna que distingue los tipos.
    #   polymorphic_identity="usuario" → identidad de esta clase base.
    __mapper_args__ = {
        "polymorphic_on": rol,
        "polymorphic_identity": "usuario",
    }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(run={self.run_usuario}, nombre={self.nombre!r})"


# ──────────────────────────────────────────────────────────────────────────────
# PacienteORM: rol PACIENTE.
# Sus citas y derivaciones se modelarán como relaciones cuando existan esas
# tablas (pasos siguientes); por ahora no agrega columnas propias.
# ──────────────────────────────────────────────────────────────────────────────

class PacienteORM(UsuarioORM):
    __mapper_args__ = {"polymorphic_identity": RolUsuario.PACIENTE}


# ──────────────────────────────────────────────────────────────────────────────
# MedicoORM: rol MEDICO.
# Tiene una especialidad (FK a la tabla especialidades). La agenda y las
# derivaciones emitidas se agregarán como relaciones en pasos futuros.
# ──────────────────────────────────────────────────────────────────────────────

class MedicoORM(UsuarioORM):
    # especialidad_id: FK hacia especialidades.id. Es NULA para los demás roles
    # (consecuencia de la herencia de tabla única), pero un médico siempre debe
    # tener especialidad: esa regla la garantiza la lógica de dominio/servicios.
    especialidad_id: Mapped[int | None] = mapped_column(
        ForeignKey("especialidades.id"), nullable=True
    )

    # especialidad: lado "muchos-a-uno". Apunta de vuelta a EspecialidadORM.medicos.
    especialidad: Mapped["EspecialidadORM | None"] = relationship(
        back_populates="medicos"
    )

    # agenda: relación UNO-A-UNO (uselist=False). Cada médico tiene exactamente
    # una agenda propia (composición del dominio). La FK vive en la tabla agendas.
    agenda: Mapped["AgendaORM"] = relationship(
        back_populates="medico", uselist=False
    )

    # clinicas: MUCHOS-A-MUCHOS con ClinicaORM vía "clinica_medicos". Un médico
    # puede trabajar en varias clínicas (sucursales) y una clínica tiene varios.
    clinicas: Mapped[list["ClinicaORM"]] = relationship(
        secondary="clinica_medicos", back_populates="medicos"
    )

    __mapper_args__ = {"polymorphic_identity": RolUsuario.MEDICO}


# ──────────────────────────────────────────────────────────────────────────────
# RecepcionistaORM: rol RECEPCIONISTA.
# Trabaja en una clínica; la FK a `clinicas` se agregará cuando exista esa tabla.
# ──────────────────────────────────────────────────────────────────────────────

class RecepcionistaORM(UsuarioORM):
    # clinica_rut: FK a la clínica donde trabaja. Nula para los demás roles.
    clinica_rut: Mapped[str | None] = mapped_column(
        ForeignKey("clinicas.rut_empresa"), nullable=True
    )

    # clinica: lado "muchos-a-uno". Varias recepcionistas por clínica.
    clinica: Mapped["ClinicaORM | None"] = relationship(
        back_populates="recepcionistas"
    )

    __mapper_args__ = {"polymorphic_identity": RolUsuario.RECEPCIONISTA}


# ──────────────────────────────────────────────────────────────────────────────
# AdministradorORM: rol ADMINISTRADOR. Acceso completo al sistema.
# ──────────────────────────────────────────────────────────────────────────────

class AdministradorORM(UsuarioORM):
    __mapper_args__ = {"polymorphic_identity": RolUsuario.ADMINISTRADOR}
