"""Casos de uso sobre clínicas.

CRUD simple con una validación de unicidad sobre el RUT. Las clínicas son el
contenedor donde viven médicos, especialidades y listas de espera, así que estos
casos de uso son la puerta para poblar el resto del sistema.
"""

from sqlalchemy.orm import Session

from app.backend.models.clinica import ClinicaORM
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
