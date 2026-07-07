"""Liberación automática de cupos y ofertas de la lista de espera.

Cubre el flujo completo a nivel de servicio (sin web): al liberarse una hora se
ofrece al paciente de mayor prioridad, y este puede confirmarla (crea su cita
PENDIENTE y sale de la lista), dejarla pasar (sigue esperando y la hora cae al
siguiente) o salir de la lista.
"""

from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.backend.domain.enums import EstadoCita, EstadoOferta, PrioridadEspera
from app.backend.models.oferta_cupo import OfertaCupoORM
from app.backend.models.usuarios import MedicoORM
from app.backend.repositories.lista_espera import RepositorioListaEspera
from app.backend.schemas.agendas import AgendaCrear, BloqueHorarioCrear
from app.backend.schemas.citas import CitaCrear
from app.backend.schemas.clinica import ClinicaCrear
from app.backend.schemas.especialidades import EspecialidadCrear
from app.backend.schemas.lista_espera import InscripcionCrear, ListaEsperaCrear
from app.backend.schemas.usuarios import MedicoCrear, PacienteCrear
from app.backend.services import lista_espera_service as les
from app.backend.services.agendas_service import agregar_horario, crear_agenda
from app.backend.services.citas_service import cancelar_cita, crear_cita
from app.backend.services.clinica_service import crear_clinica
from app.backend.services.especialidades_service import crear_especialidad
from app.backend.services.usuarios_service import crear_medico, crear_paciente

CLINICA_RUT = "76000000-0"
MEDICO_RUN = 22000001
PAC_NORMAL, PAC_ALTA, PAC_URGENTE = 30000001, 30000002, 30000003
PAC_CITA = 30000009


def _prox_slot(hora: int = 9) -> datetime:
    """Datetime en un día hábil futuro, dentro del horario del médico (08–20)."""
    dia = datetime.now().date() + timedelta(days=1)
    while dia.weekday() >= 5:  # salta sábado/domingo
        dia += timedelta(days=1)
    return datetime.combine(dia, time(hora, 0))


def _armar(db):
    """Especialidad + clínica + médico con agenda + 3 pacientes en cola por prioridad."""
    esp = crear_especialidad(db, EspecialidadCrear(nombre="Cardiología", descripcion=""))
    clinica = crear_clinica(
        db, ClinicaCrear(rut_empresa=CLINICA_RUT, nombre="Clínica Test", direccion="Calle 1")
    )
    crear_medico(db, MedicoCrear(
        run_usuario=MEDICO_RUN, nombre="Dra. Ana", correo="ana@e.cl",
        telefono=1, especialidad_id=esp.id,
    ))
    agenda = crear_agenda(db, AgendaCrear(medico_run=MEDICO_RUN))
    for dia in range(5):  # lun–vie 08:00–20:00
        agregar_horario(db, agenda.id, BloqueHorarioCrear(
            dia_semana=dia, hora_inicio=time(8, 0), hora_fin=time(20, 0),
        ))
    clinica.medicos.append(db.get(MedicoORM, MEDICO_RUN))
    clinica.especialidades.append(esp)
    db.commit()

    for run, nombre in [
        (PAC_NORMAL, "Normal"), (PAC_ALTA, "Alta"),
        (PAC_URGENTE, "Urgente"), (PAC_CITA, "Dueño"),
    ]:
        crear_paciente(db, PacienteCrear(
            run_usuario=run, nombre=nombre, correo=f"p{run}@e.cl", telefono=run,
        ))

    lista = les.obtener_o_crear_lista(
        db, ListaEsperaCrear(especialidad_id=esp.id, clinica_rut=CLINICA_RUT)
    )
    les.inscribir_paciente(db, lista.id, InscripcionCrear(paciente_id=PAC_NORMAL, prioridad=PrioridadEspera.NORMAL))
    les.inscribir_paciente(db, lista.id, InscripcionCrear(paciente_id=PAC_ALTA, prioridad=PrioridadEspera.ALTA))
    les.inscribir_paciente(db, lista.id, InscripcionCrear(paciente_id=PAC_URGENTE, prioridad=PrioridadEspera.URGENTE))
    return esp, lista


def _pendientes(db):
    return list(db.scalars(
        select(OfertaCupoORM).where(OfertaCupoORM.estado == EstadoOferta.PENDIENTE)
    ))


def _sigue_en_lista(db, lista_id, paciente_id) -> bool:
    return RepositorioListaEspera(db).inscripcion_de_paciente(lista_id, paciente_id) is not None


def test_ofrecer_cupo_va_al_de_mayor_prioridad(db):
    _esp, lista = _armar(db)

    oferta = les.ofrecer_cupo_a_lista(db, lista.id)

    assert oferta is not None
    assert oferta.paciente_id == PAC_URGENTE           # URGENTE va primero
    assert oferta.estado == EstadoOferta.PENDIENTE


def test_solo_una_oferta_pendiente_por_lista(db):
    _esp, lista = _armar(db)

    les.ofrecer_cupo_a_lista(db, lista.id)
    segunda = les.ofrecer_cupo_a_lista(db, lista.id)

    assert segunda is None
    assert len(_pendientes(db)) == 1


def test_cancelar_una_cita_dispara_la_oferta_automaticamente(db):
    _esp, lista = _armar(db)
    cita = crear_cita(db, CitaCrear(
        paciente_id=PAC_CITA, medico_id=MEDICO_RUN, inicio=_prox_slot(9), motivo="Control",
    ))
    assert _pendientes(db) == []                        # aún nadie recibió oferta

    cancelar_cita(db, cita.id)                          # libera el cupo → evento

    pendientes = _pendientes(db)
    assert len(pendientes) == 1
    assert pendientes[0].paciente_id == PAC_URGENTE


def test_aceptar_oferta_crea_cita_pendiente_y_saca_de_la_lista(db):
    _esp, lista = _armar(db)
    oferta = les.ofrecer_cupo_a_lista(db, lista.id)

    cita = les.aceptar_oferta(db, oferta.id, PAC_URGENTE)

    assert cita.estado == EstadoCita.PENDIENTE
    assert cita.paciente_id == PAC_URGENTE
    db.refresh(oferta)
    assert oferta.estado == EstadoOferta.ACEPTADA
    assert not _sigue_en_lista(db, lista.id, PAC_URGENTE)


def test_seguir_esperando_pasa_la_hora_al_siguiente(db):
    _esp, lista = _armar(db)
    oferta = les.ofrecer_cupo_a_lista(db, lista.id)     # → PAC_URGENTE

    les.seguir_esperando(db, oferta.id, PAC_URGENTE)

    db.refresh(oferta)
    assert oferta.estado == EstadoOferta.RECHAZADA
    assert _sigue_en_lista(db, lista.id, PAC_URGENTE)   # sigue esperando
    pendientes = _pendientes(db)
    assert len(pendientes) == 1
    assert pendientes[0].paciente_id == PAC_ALTA        # la hora cayó al siguiente


def test_salir_saca_de_la_lista_y_ofrece_al_siguiente(db):
    _esp, lista = _armar(db)
    oferta = les.ofrecer_cupo_a_lista(db, lista.id)     # → PAC_URGENTE

    les.salir_de_la_lista(db, oferta.id, PAC_URGENTE)

    assert not _sigue_en_lista(db, lista.id, PAC_URGENTE)
    pendientes = _pendientes(db)
    assert len(pendientes) == 1
    assert pendientes[0].paciente_id == PAC_ALTA


# ── Acción manual de la recepcionista: ofrecer (no asignar) el cupo ────────────

def test_ofrecer_siguiente_cupo_crea_oferta_para_el_top(db):
    _esp, lista = _armar(db)

    oferta = les.ofrecer_siguiente_cupo(db, lista.id)

    assert oferta.paciente_id == PAC_URGENTE
    assert oferta.estado == EstadoOferta.PENDIENTE
    # No se creó ninguna cita: la hora queda pendiente de que el paciente la acepte.
    from app.backend.models.citas import CitaORM
    assert list(db.scalars(select(CitaORM))) == []


def test_ofrecer_siguiente_cupo_falla_si_ya_hay_una_oferta_pendiente(db):
    _esp, lista = _armar(db)
    les.ofrecer_siguiente_cupo(db, lista.id)

    with pytest.raises(les.OfertaYaPendiente):
        les.ofrecer_siguiente_cupo(db, lista.id)


def test_ofrecer_siguiente_cupo_falla_si_la_cola_esta_vacia(db):
    _esp, _lista = _armar(db)
    otra = crear_especialidad(db, EspecialidadCrear(nombre="Pediatría", descripcion=""))
    vacia = les.obtener_o_crear_lista(
        db, ListaEsperaCrear(especialidad_id=otra.id, clinica_rut=CLINICA_RUT)
    )

    with pytest.raises(les.ColaVacia):
        les.ofrecer_siguiente_cupo(db, vacia.id)
