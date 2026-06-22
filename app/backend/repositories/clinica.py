"""Repositorio de clínicas."""

from sqlalchemy.orm import Session

from app.backend.models.clinica import ClinicaORM
from app.backend.repositories.base import RepositorioBase


class RepositorioClinicas(RepositorioBase[ClinicaORM]):
    """Acceso a datos de la tabla `clinicas`.

    La clave primaria es el RUT (texto), así que `obtener(rut)` de la base
    sirve para buscar una clínica por su identificador.
    """

    def __init__(self, db: Session):
        super().__init__(db, ClinicaORM)
