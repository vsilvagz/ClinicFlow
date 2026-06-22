"""Repositorio de listas de espera e inscripciones."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.lista_espera import InscripcionEsperaORM, ListaEsperaORM
from app.backend.repositories.base import RepositorioBase


class RepositorioListaEspera(RepositorioBase[ListaEsperaORM]):
    """Acceso a datos de las tablas `listas_espera` e `inscripciones_espera`."""

    def __init__(self, db: Session):
        super().__init__(db, ListaEsperaORM)

    def obtener_por_especialidad_clinica(
        self, especialidad_id: int, clinica_rut: str
    ) -> ListaEsperaORM | None:
        """Busca la lista de una especialidad en una clínica (es única por ese par)."""
        return self.db.scalar(
            select(ListaEsperaORM).where(
                ListaEsperaORM.especialidad_id == especialidad_id,
                ListaEsperaORM.clinica_rut == clinica_rut,
            )
        )

    def inscripciones_de(self, lista_id: int) -> list[InscripcionEsperaORM]:
        """Todas las inscripciones de una lista (sin ordenar)."""
        return list(
            self.db.scalars(
                select(InscripcionEsperaORM).where(
                    InscripcionEsperaORM.lista_id == lista_id
                )
            )
        )

    def inscripcion_de_paciente(
        self, lista_id: int, paciente_id: int
    ) -> InscripcionEsperaORM | None:
        """Inscripción de un paciente concreto en una lista, si existe."""
        return self.db.scalar(
            select(InscripcionEsperaORM).where(
                InscripcionEsperaORM.lista_id == lista_id,
                InscripcionEsperaORM.paciente_id == paciente_id,
            )
        )
