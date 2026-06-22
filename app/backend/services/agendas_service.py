"""Casos de uso sobre la agenda médica.

Como en `citas_service`, la decisión de diseño es REUTILIZAR la entidad de
dominio `Agenda` en lugar de reimplementar sus reglas. Para consultar
disponibilidad se reconstruye una `Agenda` de dominio a partir de la fila ORM
(con sus horarios, bloqueos, suspensiones y citas activas) y se delega en sus
métodos `esta_disponible` y `slots_disponibles`.

La suspensión merece atención especial: debe afectar a las citas existentes.
Aquí se reutiliza la lógica del dominio (`Suspension` y la máquina de estados de
`Cita`) para cancelar las citas activas del período.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.backend.domain.agenda import Agenda, BloqueHorario, Suspension
from app.backend.domain.errores import MedicoNoEncontrado
from app.backend.models.agenda import (
    AgendaORM,
    BloqueHorarioORM,
    BloqueoORM,
    SuspensionORM,
)
from app.backend.models.citas import CitaORM
from app.backend.repositories.agendas import RepositorioAgendas
from app.backend.repositories.citas import RepositorioCitas
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.agendas import (
    AgendaCrear,
    BloqueHorarioCrear,
    BloqueoCrear,
    SuspensionCrear,
)

# Reutilizamos el traductor de citas para no duplicar el mapeo ORM ↔ dominio.
from app.backend.services.citas_service import _a_dominio as _cita_a_dominio


class AgendaYaExiste(Exception):
    """El médico ya tiene una agenda creada."""


class AgendaNoEncontrada(Exception):
    """No se encontró la agenda solicitada."""


# ──────────────────────────────────────────────────────────────────────────────
# Reconstrucción ORM → dominio (para consultas de disponibilidad).
# ──────────────────────────────────────────────────────────────────────────────

def _a_dominio(db: Session, orm: AgendaORM) -> Agenda:
    """Rehidrata una `Agenda` de dominio con todas sus reglas de calendario."""
    agenda = Agenda(
        duracion_slot_minutos=orm.duracion_slot_minutos,
        capacidad_maxima_dia=orm.capacidad_maxima_dia,
    )
    for h in orm.horarios:
        agenda.agregar_horario(BloqueHorario(h.dia_semana, h.hora_inicio, h.hora_fin))
    for b in orm.bloqueos:
        agenda.bloquear(b.inicio, b.fin, b.motivo)
    # Las suspensiones se cargan antes que las citas: como la agenda aún no tiene
    # citas, `suspender` no cancela nada y solo registra el período suspendido.
    for s in orm.suspensiones:
        agenda.suspender(s.inicio, s.fin, s.motivo)
    # Las citas se localizan por el RUN del médico (no por la FK opcional a la
    # agenda): así la disponibilidad considera todas las citas activas del médico.
    citas = RepositorioCitas(db).listar_activas_de_medico(orm.medico_run)
    agenda.cargar_citas([_cita_a_dominio(c) for c in citas])
    return agenda


def _obtener_o_error(db: Session, agenda_id: int) -> AgendaORM:
    orm = RepositorioAgendas(db).obtener(agenda_id)
    if orm is None:
        raise AgendaNoEncontrada(f"No existe la agenda {agenda_id}.")
    return orm


# ──────────────────────────────────────────────────────────────────────────────
# Casos de uso.
# ──────────────────────────────────────────────────────────────────────────────

def crear_agenda(db: Session, datos: AgendaCrear) -> AgendaORM:
    """Crea la agenda de un médico (uno-a-uno), validando que exista y no la tenga."""
    repo = RepositorioAgendas(db)
    if RepositorioUsuarios(db).obtener_medico(datos.medico_run) is None:
        raise MedicoNoEncontrado(f"No existe un médico con RUN {datos.medico_run}.")
    if repo.obtener_por_medico(datos.medico_run) is not None:
        raise AgendaYaExiste(f"El médico {datos.medico_run} ya tiene una agenda.")

    agenda = AgendaORM(
        medico_run=datos.medico_run,
        duracion_slot_minutos=datos.duracion_slot_minutos,
        capacidad_maxima_dia=datos.capacidad_maxima_dia,
    )
    repo.agregar(agenda)
    db.commit()
    db.refresh(agenda)
    return agenda


def agregar_horario(
    db: Session, agenda_id: int, datos: BloqueHorarioCrear
) -> BloqueHorarioORM:
    """Agrega una franja de atención recurrente a la agenda."""
    agenda = _obtener_o_error(db, agenda_id)
    if datos.hora_inicio >= datos.hora_fin:
        raise ValueError("La hora de inicio debe ser anterior a la hora de fin.")

    horario = BloqueHorarioORM(
        agenda_id=agenda.id,
        dia_semana=datos.dia_semana,
        hora_inicio=datos.hora_inicio,
        hora_fin=datos.hora_fin,
    )
    db.add(horario)
    db.commit()
    db.refresh(horario)
    return horario


def bloquear_horario(db: Session, agenda_id: int, datos: BloqueoCrear) -> BloqueoORM:
    """Bloquea un intervalo puntual (no cancela citas ya agendadas)."""
    agenda = _obtener_o_error(db, agenda_id)
    if datos.inicio >= datos.fin:
        raise ValueError("El inicio del bloqueo debe ser anterior a su fin.")

    bloqueo = BloqueoORM(
        agenda_id=agenda.id,
        inicio=datos.inicio,
        fin=datos.fin,
        motivo=datos.motivo,
    )
    db.add(bloqueo)
    db.commit()
    db.refresh(bloqueo)
    return bloqueo


def suspender_agenda(
    db: Session, agenda_id: int, datos: SuspensionCrear
) -> tuple[SuspensionORM, list[CitaORM]]:
    """Suspende la agenda en un período y CANCELA las citas activas afectadas.

    Devuelve la suspensión creada y la lista de citas canceladas. La cancelación
    pasa por la máquina de estados del dominio (`Cita.cancelar`), de modo que las
    reglas viven en un solo lugar.
    """
    agenda = _obtener_o_error(db, agenda_id)
    if datos.inicio >= datos.fin:
        raise ValueError("El inicio de la suspensión debe ser anterior a su fin.")

    suspension_dom = Suspension(inicio=datos.inicio, fin=datos.fin, motivo=datos.motivo)
    canceladas: list[CitaORM] = []
    for cita_orm in RepositorioCitas(db).listar_activas_de_medico(agenda.medico_run):
        if suspension_dom.se_solapa_con(cita_orm.inicio, cita_orm.fin):
            cita_dom = _cita_a_dominio(cita_orm)
            cita_dom.cancelar()              # valida la transición de estado.
            cita_orm.estado = cita_dom.estado
            canceladas.append(cita_orm)

    suspension = SuspensionORM(
        agenda_id=agenda.id,
        inicio=datos.inicio,
        fin=datos.fin,
        motivo=datos.motivo,
    )
    db.add(suspension)
    db.commit()
    db.refresh(suspension)
    return suspension, canceladas


def consultar_disponibilidad(
    db: Session,
    agenda_id: int,
    inicio: datetime,
    duracion_minutos: int | None = None,
) -> bool:
    """Indica si un horario puntual está disponible en la agenda."""
    agenda = _a_dominio(db, _obtener_o_error(db, agenda_id))
    return agenda.esta_disponible(inicio, duracion_minutos)


def slots_disponibles(db: Session, agenda_id: int, fecha: date) -> list[datetime]:
    """Lista las horas libres de la agenda en una fecha."""
    agenda = _a_dominio(db, _obtener_o_error(db, agenda_id))
    return agenda.slots_disponibles(fecha)
