"""Casos de uso sobre usuarios y sus roles.

Cada rol se crea con su propia subclase ORM (herencia de tabla única). El
servicio valida las reglas que el esquema no puede comprobar por sí solo, como
que la especialidad de un médico exista realmente.
"""

from sqlalchemy.orm import Session

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


def crear_paciente(db: Session, datos: PacienteCrear) -> PacienteORM:
    _verificar_run_libre(db, datos.run_usuario)
    paciente = PacienteORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
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
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def listar_usuarios(db: Session) -> list[UsuarioORM]:
    return RepositorioUsuarios(db).listar()


def listar_medicos(db: Session) -> list[MedicoORM]:
    return RepositorioUsuarios(db).listar_medicos()


def obtener_medico(db: Session, run: int) -> MedicoORM:
    medico = RepositorioUsuarios(db).obtener_medico(run)
    if medico is None:
        raise MedicoNoEncontrado(f"No existe un médico con RUN {run}.")
    return medico
