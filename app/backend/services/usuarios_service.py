"""Casos de uso sobre usuarios y sus roles.

Cada rol se crea con su propia subclase ORM (herencia de tabla única). El
servicio valida las reglas que el esquema no puede comprobar por sí solo, como
que la especialidad de un médico exista realmente.
"""

from sqlalchemy.orm import Session

from app.backend.core.security import hash_password, verificar_password
from app.backend.domain.errores import MedicoNoEncontrado
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import (
    AdministradorORM,
    MedicoORM,
    PacienteORM,
    RecepcionistaORM,
    UsuarioORM,
)
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.usuarios import (
    AdministradorCrear,
    MedicoCrear,
    PacienteCrear,
    RecepcionistaCrear,
)


class UsuarioYaExiste(Exception):
    """Ya hay un usuario registrado con ese RUN."""


class EspecialidadNoEncontrada(Exception):
    """La especialidad indicada para el médico no existe."""


def _verificar_run_libre(db: Session, run: int) -> None:
    if db.get(UsuarioORM, run) is not None:
        raise UsuarioYaExiste(f"Ya existe un usuario con RUN {run}.")


def _hash(datos) -> str:
    """Hash de la contraseña si se entregó; cadena vacía si el usuario no tendrá login."""
    return hash_password(datos.password) if datos.password else ""


def crear_paciente(db: Session, datos: PacienteCrear) -> PacienteORM:
    _verificar_run_libre(db, datos.run_usuario)
    paciente = PacienteORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        password_hash=_hash(datos),
    )
    db.add(paciente)
    db.commit()
    db.refresh(paciente)
    return paciente


def crear_medico(db: Session, datos: MedicoCrear) -> MedicoORM:
    _verificar_run_libre(db, datos.run_usuario)
    if db.get(EspecialidadORM, datos.especialidad_id) is None:
        raise EspecialidadNoEncontrada(
            f"No existe la especialidad con id {datos.especialidad_id}."
        )

    medico = MedicoORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        especialidad_id=datos.especialidad_id,
        password_hash=_hash(datos),
    )
    db.add(medico)
    db.commit()
    db.refresh(medico)
    return medico


def crear_recepcionista(db: Session, datos: RecepcionistaCrear) -> RecepcionistaORM:
    _verificar_run_libre(db, datos.run_usuario)
    recepcionista = RecepcionistaORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        clinica_rut=datos.clinica_rut,
        password_hash=_hash(datos),
    )
    db.add(recepcionista)
    db.commit()
    db.refresh(recepcionista)
    return recepcionista


def crear_administrador(db: Session, datos: AdministradorCrear) -> AdministradorORM:
    _verificar_run_libre(db, datos.run_usuario)
    admin = AdministradorORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        password_hash=_hash(datos),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def listar_usuarios(db: Session) -> list[UsuarioORM]:
    return RepositorioUsuarios(db).listar()


def listar_medicos(db: Session) -> list[MedicoORM]:
    return RepositorioUsuarios(db).listar_medicos()


def listar_pacientes(db: Session) -> list[PacienteORM]:
    return RepositorioUsuarios(db).listar_pacientes()


def obtener_paciente(db: Session, run: int) -> PacienteORM | None:
    """Devuelve el paciente con ese RUN, o None si no está registrado."""
    return RepositorioUsuarios(db).obtener_paciente(run)


def listar_medicos_por_especialidad(db: Session, especialidad_id: int) -> list[MedicoORM]:
    return RepositorioUsuarios(db).listar_medicos_por_especialidad(especialidad_id)


def autenticar(db: Session, run: int, password: str) -> UsuarioORM | None:
    """Valida las credenciales y devuelve el usuario, o None si no calzan.

    Falla (devuelve None) tanto si el usuario no existe como si la contraseña es
    incorrecta o el usuario no tiene credenciales configuradas.
    """
    usuario = db.get(UsuarioORM, run)
    if usuario is None or not verificar_password(password, usuario.password_hash):
        return None
    return usuario


def obtener_medico(db: Session, run: int) -> MedicoORM:
    medico = RepositorioUsuarios(db).obtener_medico(run)
    if medico is None:
        raise MedicoNoEncontrado(f"No existe un médico con RUN {run}.")
    return medico
