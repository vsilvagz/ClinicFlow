"""Casos de uso sobre la lista de espera.

Gestiona la cola de pacientes que esperan un cupo en una especialidad de una
clínica. El orden de atención lo da la prioridad y, dentro del mismo nivel, la
antigüedad de la inscripción: para no duplicar ese criterio se reutiliza el mapa
de pesos de prioridad definido en el dominio (`_PESO_PRIORIDAD`).
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend import events
from app.backend.domain.enums import EstadoOferta
from app.backend.domain.errores import (
    ClinicFlowError,
    PacienteNoEncontrado,
    PacienteYaEnEspera,
)

# Reutilizamos el orden canónico de prioridades del dominio (única fuente de verdad).
from app.backend.domain.lista_espera import _PESO_PRIORIDAD
from app.backend.models.citas import CitaORM
from app.backend.models.clinica import ClinicaORM
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.lista_espera import InscripcionEsperaORM, ListaEsperaORM
from app.backend.models.mensajes import MensajeORM
from app.backend.models.oferta_cupo import OfertaCupoORM
from app.backend.models.usuarios import MedicoORM
from app.backend.repositories.agendas import RepositorioAgendas
from app.backend.repositories.lista_espera import RepositorioListaEspera
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.citas import CitaCrear
from app.backend.schemas.lista_espera import InscripcionCrear, ListaEsperaCrear
from app.backend.services.agendas_service import slots_disponibles_de_medico
from app.backend.services.citas_service import crear_cita

# Ventana (en días) en la que se busca la primera hora libre para asignar el cupo.
DIAS_HORIZONTE_CUPO = 90


class ListaEsperaNoEncontrada(Exception):
    """No se encontró la lista de espera solicitada."""


class ColaVacia(Exception):
    """No hay pacientes en espera a quienes asignar un cupo."""


class SinCupoDisponible(Exception):
    """Ningún médico de la especialidad tiene una hora libre para asignar."""


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


def _medicos_de_lista(db: Session, lista: ListaEsperaORM) -> list[MedicoORM]:
    """Médicos de la especialidad de la lista que atienden en su clínica."""
    medicos = RepositorioUsuarios(db).listar_medicos_por_especialidad(
        lista.especialidad_id
    )
    return [
        m for m in medicos
        if any(c.rut_empresa == lista.clinica_rut for c in m.clinicas)
    ]


def _proximo_cupo(
    db: Session, lista: ListaEsperaORM, ahora: datetime
) -> tuple[MedicoORM, datetime] | None:
    """Hora libre más próxima entre los médicos de la lista (o None si no hay).

    Recorre a cada médico día a día dentro del horizonte y se queda con la primera
    hora libre; devuelve la más temprana entre todos.
    """
    mejor: tuple[MedicoORM, datetime] | None = None
    for medico in _medicos_de_lista(db, lista):
        for dias in range(DIAS_HORIZONTE_CUPO + 1):
            dia = (ahora + timedelta(days=dias)).date()
            slots = slots_disponibles_de_medico(db, medico.run_usuario, dia, ahora)
            if slots:
                slot = min(slots)
                if mejor is None or slot < mejor[1]:
                    mejor = (medico, slot)
                break  # ya tenemos la hora más próxima de este médico.
    return mejor


def asignar_siguiente_cupo(
    db: Session, lista_id: int, ahora: datetime | None = None
) -> CitaORM:
    """Asigna la hora más próxima de la especialidad al siguiente en la cola.

    Toma al paciente con mayor prioridad (y más antiguo), crea la cita real en la
    agenda del médico con la primera hora libre y lo retira de la lista de espera.

    Lanza `ListaEsperaNoEncontrada`, `ColaVacia` si no hay a quién asignar, o
    `SinCupoDisponible` si ningún médico de la especialidad tiene horas libres.
    """
    ahora = ahora or datetime.now()
    lista = RepositorioListaEspera(db).obtener(lista_id)
    if lista is None:
        raise ListaEsperaNoEncontrada(f"No existe la lista de espera {lista_id}.")

    siguiente = siguiente_en_espera(db, lista_id)
    if siguiente is None:
        raise ColaVacia(f"La lista de espera {lista_id} no tiene pacientes.")

    cupo = _proximo_cupo(db, lista, ahora)
    if cupo is None:
        raise SinCupoDisponible(
            "No hay horas libres en la especialidad para asignar un cupo."
        )
    medico, inicio = cupo

    agenda = RepositorioAgendas(db).obtener_por_medico(medico.run_usuario)
    duracion = agenda.duracion_slot_minutos if agenda else 30

    # crear_cita valida y persiste la cita (queda reflejada en la agenda del médico).
    cita = crear_cita(
        db,
        CitaCrear(
            paciente_id=siguiente.paciente_id,
            medico_id=medico.run_usuario,
            inicio=inicio,
            duracion_minutos=duracion,
            motivo="Cupo asignado desde lista de espera",
        ),
        ahora=ahora,
    )

    # Ya con la cita creada, el paciente sale de la cola.
    db.delete(siguiente)
    db.commit()
    return cita


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


# ──────────────────────────────────────────────────────────────────────────────
# Liberación automática de cupos: ofertas de hora al siguiente en espera.
#
# Cuando se libera una hora (se cancela una cita o se suspende una agenda) se
# OFRECE la primera hora disponible de la especialidad al paciente con mayor
# prioridad de la lista, y se le notifica en «Mis mensajes». El paciente decide:
# la confirma (se crea su cita PENDIENTE), la deja pasar y sigue esperando (la
# hora pasa al siguiente de la cola), o se sale de la lista. La reserva NO se
# concreta hasta que el paciente acepta, de modo que la hora siempre es una
# decisión suya y las reglas de negocio se validan al crear la cita real.
# ──────────────────────────────────────────────────────────────────────────────


class OfertaNoEncontrada(Exception):
    """No hay una oferta de cupo pendiente para ese paciente."""


class OfertaYaPendiente(Exception):
    """La lista ya tiene una oferta esperando la respuesta de un paciente."""


class HoraOfrecidaNoDisponible(ClinicFlowError):
    """Al aceptar, la hora ofrecida ya había sido tomada por alguien más."""


def _oferta_pendiente_de_lista(db: Session, lista_id: int) -> OfertaCupoORM | None:
    """Oferta aún sin responder de una lista (a lo más una a la vez por lista)."""
    return db.scalar(
        select(OfertaCupoORM).where(
            OfertaCupoORM.lista_id == lista_id,
            OfertaCupoORM.estado == EstadoOferta.PENDIENTE,
        )
    )


def _oferta_pendiente_de_paciente(db: Session, paciente_id: int) -> OfertaCupoORM | None:
    """Oferta aún sin responder de un paciente (para no ofrecerle dos a la vez)."""
    return db.scalar(
        select(OfertaCupoORM).where(
            OfertaCupoORM.paciente_id == paciente_id,
            OfertaCupoORM.estado == EstadoOferta.PENDIENTE,
        )
    )


def _rechazo_esta_hora(
    db: Session, lista_id: int, paciente_id: int, medico_id: int, inicio: datetime
) -> bool:
    """True si el paciente ya rechazó exactamente esta hora (para pasarla al siguiente)."""
    return db.scalar(
        select(OfertaCupoORM).where(
            OfertaCupoORM.lista_id == lista_id,
            OfertaCupoORM.paciente_id == paciente_id,
            OfertaCupoORM.medico_id == medico_id,
            OfertaCupoORM.inicio == inicio,
            OfertaCupoORM.estado == EstadoOferta.RECHAZADA,
        )
    ) is not None


def _listas_de_medico(db: Session, medico: MedicoORM) -> list[ListaEsperaORM]:
    """Listas de espera de la especialidad del médico en las clínicas donde atiende."""
    if medico.especialidad_id is None:
        return []
    repo = RepositorioListaEspera(db)
    listas = []
    for clinica in medico.clinicas:
        lst = repo.obtener_por_especialidad_clinica(
            medico.especialidad_id, clinica.rut_empresa
        )
        if lst is not None:
            listas.append(lst)
    return listas


def ofrecer_cupo_a_lista(
    db: Session, lista_id: int, ahora: datetime | None = None
) -> OfertaCupoORM | None:
    """Ofrece la primera hora disponible al siguiente paciente de la cola.

    Reglas: a lo más una oferta pendiente por lista (un cupo, una oferta); se
    ofrece al paciente de mayor prioridad que no tenga ya una oferta pendiente y
    que no haya rechazado justamente esa hora (así una hora rechazada cae al
    siguiente de la cola). Devuelve la oferta creada, o None si no hay a quién o
    qué ofrecer.
    """
    ahora = ahora or datetime.now()
    lista = RepositorioListaEspera(db).obtener(lista_id)
    if lista is None or _oferta_pendiente_de_lista(db, lista_id) is not None:
        return None

    cupo = _proximo_cupo(db, lista, ahora)
    if cupo is None:
        return None
    medico, inicio = cupo

    destinatario = None
    for insc in _ordenar(RepositorioListaEspera(db).inscripciones_de(lista_id)):
        if _oferta_pendiente_de_paciente(db, insc.paciente_id) is not None:
            continue
        if _rechazo_esta_hora(db, lista_id, insc.paciente_id, medico.run_usuario, inicio):
            continue
        destinatario = insc
        break
    if destinatario is None:
        return None

    agenda = RepositorioAgendas(db).obtener_por_medico(medico.run_usuario)
    duracion = agenda.duracion_slot_minutos if agenda else 30

    oferta = OfertaCupoORM(
        paciente_id=destinatario.paciente_id,
        lista_id=lista_id,
        medico_id=medico.run_usuario,
        medico_nombre=medico.nombre,
        especialidad=lista.especialidad.nombre,
        inicio=inicio,
        duracion_minutos=duracion,
        estado=EstadoOferta.PENDIENTE,
    )
    db.add(oferta)
    db.commit()
    db.refresh(oferta)
    return oferta


def ofrecer_siguiente_cupo(
    db: Session, lista_id: int, ahora: datetime | None = None
) -> OfertaCupoORM:
    """Ofrece (sin asignar) la próxima hora al siguiente en espera, con validación explícita.

    Es la acción MANUAL de la recepcionista: en lugar de crear la cita
    directamente, crea una oferta que el paciente debe confirmar o rechazar desde
    «Mis mensajes». A diferencia de `ofrecer_cupo_a_lista` (best-effort, para la
    automatización), aquí se lanzan errores claros para informar a la recepción:
    `ListaEsperaNoEncontrada`, `OfertaYaPendiente` si ya hay una oferta sin
    responder, `ColaVacia` si no hay pacientes, o `SinCupoDisponible` si no hay
    horas libres.
    """
    ahora = ahora or datetime.now()
    if RepositorioListaEspera(db).obtener(lista_id) is None:
        raise ListaEsperaNoEncontrada(f"No existe la lista de espera {lista_id}.")
    if _oferta_pendiente_de_lista(db, lista_id) is not None:
        raise OfertaYaPendiente(
            f"La lista {lista_id} ya tiene una oferta esperando la respuesta del paciente."
        )
    if siguiente_en_espera(db, lista_id) is None:
        raise ColaVacia(f"La lista de espera {lista_id} no tiene pacientes.")

    oferta = ofrecer_cupo_a_lista(db, lista_id, ahora)
    if oferta is None:
        raise SinCupoDisponible(
            "No hay horas libres en la especialidad para ofrecer un cupo."
        )
    return oferta


def ofertas_pendientes_de_paciente(db: Session, paciente_id: int) -> list[OfertaCupoORM]:
    """Ofertas de cupo aún sin responder de un paciente (para «Mis mensajes»)."""
    return list(
        db.scalars(
            select(OfertaCupoORM)
            .where(
                OfertaCupoORM.paciente_id == paciente_id,
                OfertaCupoORM.estado == EstadoOferta.PENDIENTE,
            )
            .order_by(OfertaCupoORM.creada_en.desc())
        )
    )


def _oferta_pendiente_o_error(
    db: Session, oferta_id: int, paciente_id: int
) -> OfertaCupoORM:
    """Carga la oferta si está pendiente y pertenece al paciente; si no, lanza error."""
    oferta = db.get(OfertaCupoORM, oferta_id)
    if (
        oferta is None
        or oferta.paciente_id != paciente_id
        or oferta.estado != EstadoOferta.PENDIENTE
    ):
        raise OfertaNoEncontrada(
            f"No hay una oferta pendiente {oferta_id} para el paciente {paciente_id}."
        )
    return oferta


def _notificar(db: Session, paciente_id: int, texto: str) -> None:
    """Deja una notificación de texto en «Mis mensajes» del paciente."""
    db.add(MensajeORM(paciente_id=paciente_id, tipo="LISTA_ESPERA", contenido=texto))


def aceptar_oferta(
    db: Session, oferta_id: int, paciente_id: int, ahora: datetime | None = None
) -> CitaORM:
    """El paciente confirma la hora ofrecida: se crea su cita (PENDIENTE) y sale de la lista.

    Si la hora fue tomada por otra persona entre la oferta y la respuesta, la
    oferta se rechaza, el paciente queda notificado y sigue en la lista, y la hora
    se ofrece al siguiente; se lanza `HoraOfrecidaNoDisponible`.
    """
    ahora = ahora or datetime.now()
    oferta = _oferta_pendiente_o_error(db, oferta_id, paciente_id)

    try:
        cita = crear_cita(
            db,
            CitaCrear(
                paciente_id=paciente_id,
                medico_id=oferta.medico_id,
                inicio=oferta.inicio,
                duracion_minutos=oferta.duracion_minutos,
                motivo="Hora asignada desde lista de espera",
            ),
            ahora=ahora,
        )
    except ClinicFlowError as exc:
        oferta.estado = EstadoOferta.RECHAZADA
        _notificar(
            db, paciente_id,
            f"La hora de {oferta.especialidad} que te ofrecimos ya no está "
            "disponible. Sigues en la lista de espera.",
        )
        db.commit()
        ofrecer_cupo_a_lista(db, oferta.lista_id, ahora)
        raise HoraOfrecidaNoDisponible(str(exc)) from exc

    oferta.estado = EstadoOferta.ACEPTADA
    inscripcion = RepositorioListaEspera(db).inscripcion_de_paciente(
        oferta.lista_id, paciente_id
    )
    if inscripcion is not None:
        db.delete(inscripcion)
    _notificar(
        db, paciente_id,
        f"Confirmaste tu hora de {oferta.especialidad} con {oferta.medico_nombre} "
        f"el {oferta.inicio.strftime('%d-%m-%Y %H:%M')}. Queda pendiente de "
        "confirmación; puedes verla en «Mis citas».",
    )
    db.commit()
    return cita


def seguir_esperando(db: Session, oferta_id: int, paciente_id: int) -> None:
    """El paciente rechaza esta hora pero SIGUE en la lista; la hora pasa al siguiente."""
    oferta = _oferta_pendiente_o_error(db, oferta_id, paciente_id)
    oferta.estado = EstadoOferta.RECHAZADA
    _notificar(
        db, paciente_id,
        f"Dejaste pasar la hora de {oferta.especialidad}. Sigues en la lista de "
        "espera; te avisaremos cuando se libere otra.",
    )
    db.commit()
    # La misma hora se ofrece al siguiente de la cola (que no la haya rechazado).
    ofrecer_cupo_a_lista(db, oferta.lista_id)


def salir_de_la_lista(db: Session, oferta_id: int, paciente_id: int) -> None:
    """El paciente rechaza la hora y ADEMÁS sale de la lista de espera."""
    oferta = _oferta_pendiente_o_error(db, oferta_id, paciente_id)
    oferta.estado = EstadoOferta.RECHAZADA
    inscripcion = RepositorioListaEspera(db).inscripcion_de_paciente(
        oferta.lista_id, paciente_id
    )
    if inscripcion is not None:
        db.delete(inscripcion)
    _notificar(
        db, paciente_id,
        f"Saliste de la lista de espera de {oferta.especialidad}.",
    )
    db.commit()
    # La hora liberada se ofrece al siguiente de la cola.
    ofrecer_cupo_a_lista(db, oferta.lista_id)


# ──────────────────────────────────────────────────────────────────────────────
# Automatización: reaccionar a la cancelación de una cita ofreciendo su cupo.
# Se suscribe al bus de eventos, de modo que cualquier cancelación (desde la web,
# la recepción, el asistente o una suspensión de agenda) dispara la oferta sin
# que esos módulos conozcan la lista de espera.
# ──────────────────────────────────────────────────────────────────────────────

def _al_cancelarse_una_cita(db: Session, cita: CitaORM) -> None:
    """Ofrece el cupo liberado por una cita cancelada a la lista de su especialidad."""
    medico = RepositorioUsuarios(db).obtener_medico(cita.medico_id)
    if medico is None:
        return
    for lista in _listas_de_medico(db, medico):
        ofrecer_cupo_a_lista(db, lista.id)


events.suscribir(events.CITA_CANCELADA, _al_cancelarse_una_cita)
