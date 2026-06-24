"""Casos de uso sobre especialidades médicas.

La capa de servicios orquesta repositorios y reglas de negocio. Aquí es simple
(CRUD con una validación de unicidad), pero mantiene el patrón: la API no habla
directamente con la base de datos, sino con estos casos de uso.
"""

from sqlalchemy.orm import Session

from app.backend.domain.especialidades import Especialidad
from app.backend.domain.usuarios import Administrador, Usuario
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.schemas.especialidades import EspecialidadCrear


class EspecialidadYaExiste(Exception):
    """Ya hay una especialidad registrada con ese nombre."""


class EspecialidadNoEncontrada(Exception):
    """No se encontró la especialidad solicitada."""


def crear_especialidad(db: Session, datos: EspecialidadCrear) -> EspecialidadORM:
    """Crea una especialidad, rechazando nombres duplicados."""
    repo = RepositorioEspecialidades(db)
    if repo.obtener_por_nombre(datos.nombre) is not None:
        raise EspecialidadYaExiste(
            f"Ya existe una especialidad llamada '{datos.nombre}'."
        )

    especialidad = EspecialidadORM(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
    )
    repo.agregar(especialidad)
    db.commit()
    db.refresh(especialidad)
    return especialidad


def listar_especialidades(db: Session) -> list[EspecialidadORM]:
    """Devuelve todas las especialidades registradas."""
    return RepositorioEspecialidades(db).listar()


def obtener_especialidad(db: Session, especialidad_id: int) -> EspecialidadORM | None:
    """Devuelve la especialidad con ese id, o None si no existe."""
    return RepositorioEspecialidades(db).obtener(especialidad_id)


def editar_especialidad(
    db: Session,
    actor: UsuarioORM,
    especialidad_id: int,
    nombre: str | None = None,
    descripcion: str | None = None,
) -> EspecialidadORM:
    """Renombra o cambia la descripción de una especialidad (vía el dominio)."""
    repo = RepositorioEspecialidades(db)
    orm = repo.obtener(especialidad_id)
    if orm is None:
        raise EspecialidadNoEncontrada(f"No existe la especialidad {especialidad_id}.")

    # Unicidad del nombre: rechazar si otro registro ya usa el nombre nuevo.
    if nombre is not None:
        existente = repo.obtener_por_nombre(nombre.strip())
        if existente is not None and existente.id != especialidad_id:
            raise EspecialidadYaExiste(f"Ya existe una especialidad llamada '{nombre.strip()}'.")

    dom = Especialidad(orm.nombre, orm.descripcion)
    Administrador(actor.run_usuario, actor.nombre, actor.correo, actor.telefono).editar_especialidad(
        dom, nombre=nombre, descripcion=descripcion
    )

    orm.nombre = dom.nombre
    orm.descripcion = dom.descripcion
    db.commit()
    db.refresh(orm)
    return orm


def eliminar_especialidad(db: Session, actor: UsuarioORM, especialidad_id: int) -> int:
    """Elimina una especialidad y desactiva a sus médicos.

    Los médicos asignados quedan dados de baja y se desligan de la especialidad
    (su FK se libera) para poder borrarla. Devuelve cuántos médicos se desactivaron.
    """
    repo = RepositorioEspecialidades(db)
    orm = repo.obtener(especialidad_id)
    if orm is None:
        raise EspecialidadNoEncontrada(f"No existe la especialidad {especialidad_id}.")

    admin = Administrador(actor.run_usuario, actor.nombre, actor.correo, actor.telefono)
    desactivados = 0
    for medico in list(orm.medicos):
        dom = Usuario(medico.run_usuario, medico.nombre, medico.correo, medico.telefono)
        dom._activo = medico.activo
        admin.desactivar_usuario(dom)
        medico.activo = dom.activo
        medico.especialidad_id = None  # libera la FK para poder eliminar la especialidad
        desactivados += 1

    db.delete(orm)
    db.commit()
    return desactivados
