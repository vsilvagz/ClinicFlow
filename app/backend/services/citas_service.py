"""Casos de uso sobre citas médicas (enunciado 3.1.1).

Este servicio es el corazón de las reglas de negocio de la API. Su decisión de
diseño clave es REUTILIZAR la entidad de dominio `Cita` en lugar de reimplementar
las reglas: para validar se reconstruye un objeto `Cita` a partir de la fila ORM,
se ejecutan sus métodos (`crear`, `confirmar`, `cancelar`, `reagendar`…) —que ya
encierran la máquina de estados y la detección de conflictos— y luego se vuelca
el resultado de vuelta al ORM. Así la lógica vive en un solo lugar (`domain/`),
es testeable sin base de datos y la persistencia solo "traduce".
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.backend.domain.citas import Cita
from app.backend.domain.errores import (
    CitaDuplicadaEnPeriodo,
    CitaNoEncontrada,
    MedicoNoEncontrado,
    PacienteNoEncontrado,
)
from app.backend.models.citas import CitaORM
from app.backend.repositories.citas import RepositorioCitas
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.citas import CitaCrear, CitaReagendar

# Días mínimos que deben separar dos citas activas del mismo paciente y
# especialidad: evita que acumule varias horas de un mismo tipo muy seguidas.
DIAS_MINIMOS_ENTRE_CITAS_ESPECIALIDAD = 7


# ──────────────────────────────────────────────────────────────────────────────
# Traducción ORM ↔ dominio.
# ──────────────────────────────────────────────────────────────────────────────

def _a_dominio(orm: CitaORM) -> Cita:
    """Reconstruye la entidad de dominio a partir de la fila ORM."""
    return Cita(
        id=orm.id,
        paciente_id=orm.paciente_id,
        medico_id=orm.medico_id,
        especialidad=orm.especialidad,
        inicio=orm.inicio,
        fin=orm.fin,
        estado=orm.estado,
        motivo=orm.motivo,
        creada_en=orm.creada_en,
        notas=orm.notas,
        reagendada_desde_id=orm.reagendada_desde_id,
        reagendada_hacia_id=orm.reagendada_hacia_id,
    )


def _a_orm(cita: Cita) -> CitaORM:
    """Crea una fila ORM nueva a partir de una entidad de dominio."""
    return CitaORM(
        id=cita.id,
        paciente_id=cita.paciente_id,
        medico_id=cita.medico_id,
        especialidad=cita.especialidad,
        inicio=cita.inicio,
        fin=cita.fin,
        estado=cita.estado,
        motivo=cita.motivo,
        creada_en=cita.creada_en,
        notas=cita.notas,
        reagendada_desde_id=cita.reagendada_desde_id,
        reagendada_hacia_id=cita.reagendada_hacia_id,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Casos de uso.
# ──────────────────────────────────────────────────────────────────────────────

def crear_cita(db: Session, datos: CitaCrear, ahora: datetime | None = None) -> CitaORM:
    """Crea una cita validando paciente, médico, fecha y conflictos de agenda."""
    usuarios = RepositorioUsuarios(db)
    citas = RepositorioCitas(db)

    if usuarios.obtener_paciente(datos.paciente_id) is None:
        raise PacienteNoEncontrado(f"No existe un paciente con RUN {datos.paciente_id}.")

    medico = usuarios.obtener_medico(datos.medico_id)
    if medico is None:
        raise MedicoNoEncontrado(f"No existe un médico con RUN {datos.medico_id}.")

    # El dominio valida que la cita no quede en el pasado y calcula la hora de fin.
    especialidad = medico.especialidad.nombre if medico.especialidad else ""
    cita_dom = Cita.crear(
        paciente_id=datos.paciente_id,
        medico_id=datos.medico_id,
        especialidad=especialidad,
        inicio=datos.inicio,
        duracion_minutos=datos.duracion_minutos,
        motivo=datos.motivo,
        ahora=ahora,
    )

    # Regla: el paciente no puede tener otra cita activa de la misma especialidad
    # dentro de unos pocos días (antes o después) de la hora solicitada.
    if especialidad:
        ventana = timedelta(days=DIAS_MINIMOS_ENTRE_CITAS_ESPECIALIDAD)
        cercanas = citas.listar_activas_de_paciente_por_especialidad(
            datos.paciente_id,
            especialidad,
            cita_dom.inicio - ventana,
            cita_dom.inicio + ventana,
        )
        if cercanas:
            raise CitaDuplicadaEnPeriodo(
                f"El paciente {datos.paciente_id} ya tiene una cita de "
                f"{especialidad} dentro de {DIAS_MINIMOS_ENTRE_CITAS_ESPECIALIDAD} "
                f"días de la hora solicitada."
            )

    # Conflicto de agenda: se compara contra las citas activas del médico.
    existentes = [_a_dominio(c) for c in citas.listar_activas_de_medico(datos.medico_id)]
    cita_dom.validar_no_solapa(existentes)

    orm = citas.agregar(_a_orm(cita_dom))
    db.commit()
    db.refresh(orm)
    return orm


def _aplicar_transicion(db: Session, cita_id: UUID, accion) -> CitaORM:
    """Carga la cita, aplica una transición de estado del dominio y persiste.

    `accion` es una función que recibe la entidad `Cita` y llama al método de
    negocio adecuado (confirmar, cancelar, completar, …). Si la transición es
    inválida, el dominio lanza `TransicionEstadoInvalida` y no se guarda nada.
    """
    repo = RepositorioCitas(db)
    orm = repo.obtener(cita_id)
    if orm is None:
        raise CitaNoEncontrada(f"No existe la cita {cita_id}.")

    cita_dom = _a_dominio(orm)
    accion(cita_dom)            # puede lanzar TransicionEstadoInvalida.
    orm.estado = cita_dom.estado
    db.commit()
    db.refresh(orm)
    return orm


def confirmar_cita(db: Session, cita_id: UUID) -> CitaORM:
    return _aplicar_transicion(db, cita_id, lambda c: c.confirmar())


def cancelar_cita(db: Session, cita_id: UUID) -> CitaORM:
    return _aplicar_transicion(db, cita_id, lambda c: c.cancelar())


def completar_cita(db: Session, cita_id: UUID) -> CitaORM:
    return _aplicar_transicion(db, cita_id, lambda c: c.completar())


def marcar_no_asistio(db: Session, cita_id: UUID) -> CitaORM:
    return _aplicar_transicion(db, cita_id, lambda c: c.marcar_no_asistio())


def reagendar_cita(
    db: Session,
    cita_id: UUID,
    datos: CitaReagendar,
    ahora: datetime | None = None,
) -> CitaORM:
    """Marca la cita original como REAGENDADA y crea la cita nueva enlazada."""
    repo = RepositorioCitas(db)
    orm = repo.obtener(cita_id)
    if orm is None:
        raise CitaNoEncontrada(f"No existe la cita {cita_id}.")

    original = _a_dominio(orm)
    # El dominio transiciona la original a REAGENDADA y devuelve la cita nueva.
    nueva_dom = original.reagendar(
        nueva_inicio=datos.nueva_inicio,
        duracion_minutos=datos.duracion_minutos,
        ahora=ahora,
    )

    # La nueva cita no debe solapar con las demás citas activas del médico.
    existentes = [_a_dominio(c) for c in repo.listar_activas_de_medico(original.medico_id)]
    nueva_dom.validar_no_solapa(existentes)

    # Persistir: actualizar la original y agregar la nueva con el enlace de traza.
    orm.estado = original.estado
    orm.reagendada_hacia_id = original.reagendada_hacia_id
    nueva_orm = repo.agregar(_a_orm(nueva_dom))
    db.commit()
    db.refresh(nueva_orm)
    return nueva_orm


def listar_citas_de_paciente(db: Session, paciente_id: int) -> list[CitaORM]:
    return RepositorioCitas(db).listar_de_paciente(paciente_id)


def obtener_cita(db: Session, cita_id: UUID) -> CitaORM | None:
    """Devuelve la cita con ese id, o None si no existe."""
    return RepositorioCitas(db).obtener(cita_id)
