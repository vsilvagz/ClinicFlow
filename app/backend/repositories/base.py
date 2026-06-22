"""Repositorio base genérico para el acceso a datos.

Un repositorio encapsula el acceso a una tabla: oculta el SQL y las sesiones
detrás de métodos con nombre de negocio (`obtener`, `listar`, `agregar`…). Así
los servicios trabajan con objetos y no con consultas, y se pueden reemplazar
por dobles en los tests.

`RepositorioBase` reúne las operaciones CRUD comunes usando genéricos: cada
repositorio concreto hereda de él indicando con qué modelo ORM trabaja, y solo
agrega las consultas propias de su entidad.
"""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.core.database import Base

# ModeloORM: cualquier modelo que herede de Base (UsuarioORM, CitaORM, …).
ModeloORM = TypeVar("ModeloORM", bound=Base)


class RepositorioBase(Generic[ModeloORM]):
    """Operaciones CRUD comunes sobre un modelo ORM."""

    def __init__(self, db: Session, modelo: type[ModeloORM]):
        # db: la sesión activa (la inyecta FastAPI vía get_db).
        # modelo: la clase ORM sobre la que opera este repositorio.
        self.db = db
        self.modelo = modelo

    def obtener(self, id_) -> ModeloORM | None:
        """Devuelve una fila por su clave primaria, o None si no existe."""
        return self.db.get(self.modelo, id_)

    def listar(self) -> list[ModeloORM]:
        """Devuelve todas las filas de la tabla."""
        return list(self.db.scalars(select(self.modelo)))

    def agregar(self, obj: ModeloORM) -> ModeloORM:
        """Añade un objeto a la sesión y lo vuelca (flush) para asignarle id."""
        self.db.add(obj)
        self.db.flush()  # ejecuta el INSERT sin cerrar la transacción.
        return obj

    def eliminar(self, obj: ModeloORM) -> None:
        """Marca un objeto para eliminación."""
        self.db.delete(obj)
