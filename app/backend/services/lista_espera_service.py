"""Casos de uso sobre la lista de espera.

Gestiona la cola de pacientes que esperan un cupo en una especialidad de una
clínica. El orden de atención lo da la prioridad y, dentro del mismo nivel, la
antigüedad de la inscripción: para no duplicar ese criterio se reutiliza el mapa
de pesos de prioridad definido en el dominio (`_PESO_PRIORIDAD`).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.backend.domain.errores import PacienteNoEncontrado, PacienteYaEnEspera

# Reutilizamos el orden canónico de prioridades del dominio (única fuente de verdad).
from app.backend.domain.lista_espera import _PESO_PRIORIDAD
from app.backend.models.clinica import ClinicaORM
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.lista_espera import InscripcionEsperaORM, ListaEsperaORM
from app.backend.repositories.lista_espera import RepositorioListaEspera
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.lista_espera import InscripcionCrear, ListaEsperaCrear


class ListaEsperaNoEncontrada(Exception):
    """No se encontró la lista de espera solicitada."""


class EspecialidadNoEncontrada(Exception):
    """La especialidad indicada para la lista no existe."""


class ClinicaNoEncontrada(Exception):
    """La clínica indicada para la lista no existe."""


def _ordenar(inscripciones: list[InscripcionEsperaORM]) -> list[InscripcionEsperaORM]:
    """Ordena por prioridad (mayor urgencia primero) y luego por antigüedad."""
    return sorted(
        inscripciones,
        key=lambda i: (_PESO_PRIORIDAD[i.prioridad], i.fecha_inscripcion),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Casos de uso.
# ──────────────────────────────────────────────────────────────────────────────

def obtener_o_crear_lista(db: Session, datos: ListaEsperaCrear) -> ListaEsperaORM:
    """Devuelve la lista de la especialidad en la clínica; la crea si no existe."""
    if db.get(EspecialidadORM, datos.especialidad_id) is None:
        raise EspecialidadNoEncontrada(
            f"No existe la especialidad con id {datos.especialidad_id}."
        )
    if db.get(ClinicaORM, datos.clinica_rut) is None:
        raise ClinicaNoEncontrada(f"No existe una clínica con RUT {datos.clinica_rut}.")

    repo = RepositorioListaEspera(db)
    lista = repo.obtener_por_especialidad_clinica(
        datos.especialidad_id, datos.clinica_rut
    )
    if lista is not None:
        return lista

    lista = ListaEsperaORM(
        especialidad_id=datos.especialidad_id,
        clinica_rut=datos.clinica_rut,
    )
    repo.agregar(lista)
    db.commit()
    db.refresh(lista)
    return lista


def inscribir_paciente(
    db: Session,
    lista_id: int,
    datos: InscripcionCrear,
    fecha_inscripcion: datetime | None = None,
) -> InscripcionEsperaORM:
    """Inscribe a un paciente en una lista, evitando duplicados."""
    repo = RepositorioListaEspera(db)
    if repo.obtener(lista_id) is None:
        raise ListaEsperaNoEncontrada(f"No existe la lista de espera {lista_id}.")
    if RepositorioUsuarios(db).obtener_paciente(datos.paciente_id) is None:
        raise PacienteNoEncontrado(f"No existe un paciente con RUN {datos.paciente_id}.")
    if repo.inscripcion_de_paciente(lista_id, datos.paciente_id) is not None:
        raise PacienteYaEnEspera(
            f"El paciente {datos.paciente_id} ya está en la lista {lista_id}."
        )

    inscripcion = InscripcionEsperaORM(
        lista_id=lista_id,
        paciente_id=datos.paciente_id,
        fecha_inscripcion=fecha_inscripcion or datetime.now(),
        prioridad=datos.prioridad,
    )
    db.add(inscripcion)
    db.commit()
    db.refresh(inscripcion)
    return inscripcion


def listar_inscripciones(db: Session, lista_id: int) -> list[InscripcionEsperaORM]:
    """Inscripciones de una lista, en orden de atención."""
    repo = RepositorioListaEspera(db)
    if repo.obtener(lista_id) is None:
        raise ListaEsperaNoEncontrada(f"No existe la lista de espera {lista_id}.")
    return _ordenar(repo.inscripciones_de(lista_id))


def siguiente_en_espera(db: Session, lista_id: int) -> InscripcionEsperaORM | None:
    """Devuelve (sin retirar) al primer paciente en la cola, o None si está vacía."""
    ordenadas = listar_inscripciones(db, lista_id)
    return ordenadas[0] if ordenadas else None


def asignar_siguiente_cupo(db: Session, lista_id: int) -> InscripcionEsperaORM | None:
    """Retira y devuelve al paciente con mayor prioridad: libera el cupo para él.

    Representa la reasignación de una hora disponible al siguiente en la cola.
    Devuelve None si la lista está vacía.
    """
    siguiente = siguiente_en_espera(db, lista_id)
    if siguiente is None:
        return None
    db.delete(siguiente)
    db.commit()
    return siguiente


def retirar_paciente(db: Session, lista_id: int, paciente_id: int) -> None:
    """Saca a un paciente concreto de la lista (p. ej. si ya consiguió hora)."""
    repo = RepositorioListaEspera(db)
    inscripcion = repo.inscripcion_de_paciente(lista_id, paciente_id)
    if inscripcion is None:
        raise PacienteNoEncontrado(
            f"El paciente {paciente_id} no está en la lista {lista_id}."
        )
    db.delete(inscripcion)
    db.commit()
