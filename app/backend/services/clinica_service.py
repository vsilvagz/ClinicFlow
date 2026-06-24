"""Casos de uso sobre clínicas.

CRUD simple con una validación de unicidad sobre el RUT. Las clínicas son el
contenedor donde viven médicos, especialidades y listas de espera, así que estos
casos de uso son la puerta para poblar el resto del sistema.
"""

from sqlalchemy.orm import Session

from app.backend.domain.clinica import Clinica
from app.backend.domain.usuarios import Administrador, Usuario
from app.backend.models.clinica import ClinicaORM
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.clinica import RepositorioClinicas
from app.backend.schemas.clinica import ClinicaCrear


class ClinicaYaExiste(Exception):
    """Ya hay una clínica registrada con ese RUT."""


class ClinicaNoEncontrada(Exception):
    """No se encontró la clínica solicitada."""


def crear_clinica(db: Session, datos: ClinicaCrear) -> ClinicaORM:
    """Crea una clínica, rechazando RUT duplicados."""
    repo = RepositorioClinicas(db)
    if repo.obtener(datos.rut_empresa) is not None:
        raise ClinicaYaExiste(f"Ya existe una clínica con RUT {datos.rut_empresa}.")

    clinica = ClinicaORM(
        rut_empresa=datos.rut_empresa,
        nombre=datos.nombre,
        direccion=datos.direccion,
    )
    repo.agregar(clinica)
    db.commit()
    db.refresh(clinica)
    return clinica


def listar_clinicas(db: Session) -> list[ClinicaORM]:
    """Devuelve todas las clínicas registradas."""
    return RepositorioClinicas(db).listar()


def obtener_clinica(db: Session, rut_empresa: str) -> ClinicaORM:
    """Devuelve una clínica por su RUT o lanza ClinicaNoEncontrada."""
    clinica = RepositorioClinicas(db).obtener(rut_empresa)
    if clinica is None:
        raise ClinicaNoEncontrada(f"No existe una clínica con RUT {rut_empresa}.")
    return clinica


def editar_clinica(
    db: Session,
    actor: UsuarioORM,
    rut_empresa: str,
    nombre: str | None = None,
    direccion: str | None = None,
) -> ClinicaORM:
    """Actualiza el nombre o la dirección de una clínica (vía el dominio)."""
    orm = RepositorioClinicas(db).obtener(rut_empresa)
    if orm is None:
        raise ClinicaNoEncontrada(f"No existe una clínica con RUT {rut_empresa}.")

    dom = Clinica(orm.rut_empresa, orm.nombre, orm.direccion)
    _a_admin_dominio(actor).editar_clinica(dom, nombre=nombre, direccion=direccion)

    orm.nombre = dom.nombre
    orm.direccion = dom.direccion
    db.commit()
    db.refresh(orm)
    return orm


def eliminar_clinica(db: Session, actor: UsuarioORM, rut_empresa: str) -> int:
    """Elimina una clínica y desactiva a sus recepcionistas.

    Las recepcionistas quedan dadas de baja y se desligan de la clínica (su FK se
    libera) para poder borrarla. Devuelve cuántas recepcionistas se desactivaron.
    """
    orm = RepositorioClinicas(db).obtener(rut_empresa)
    if orm is None:
        raise ClinicaNoEncontrada(f"No existe una clínica con RUT {rut_empresa}.")

    admin = _a_admin_dominio(actor)
    desactivadas = 0
    for recep in list(orm.recepcionistas):
        dom = Usuario(recep.run_usuario, recep.nombre, recep.correo, recep.telefono)
        dom._activo = recep.activo
        admin.desactivar_usuario(dom)
        recep.activo = dom.activo
        recep.clinica_rut = None  # libera la FK para poder eliminar la clínica
        desactivadas += 1

    db.delete(orm)
    db.commit()
    return desactivadas


def _a_admin_dominio(actor: UsuarioORM) -> Administrador:
    """Reconstruye al administrador que ejecuta la acción."""
    return Administrador(actor.run_usuario, actor.nombre, actor.correo, actor.telefono)
