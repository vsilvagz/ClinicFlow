"""Tests del despachador: helpers puros y acciones de solo lectura."""

import uuid
from datetime import datetime, time, timedelta

import pytest
from app.backend.ai.despachador import (
    despachar,
    emparejar_nombre,
    formatear_citas,
)
from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.domain.enums import EstadoCita
from app.backend.models.agenda import AgendaORM, BloqueHorarioORM
from app.backend.models.citas import CitaORM
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.lista_espera import ListaEsperaORM
from app.backend.models.usuarios import MedicoORM, PacienteORM
from app.backend.repositories.citas import RepositorioCitas

MEDICO_RUN = 222222222

AHORA = datetime(2026, 6, 27, 9, 0)
PACIENTE_RUN = 111111111


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------

def test_emparejar_nombre_exacto_ignora_tildes_y_caso():
    assert emparejar_nombre("cardiologia", ["Cardiología", "Pediatría"]) == "Cardiología"


def test_emparejar_nombre_por_contencion():
    assert emparejar_nombre("cardio", ["Cardiología", "Pediatría"]) == "Cardiología"


def test_emparejar_nombre_sin_coincidencia_devuelve_none():
    assert emparejar_nombre("oftalmología", ["Cardiología"]) is None


def test_emparejar_nombre_consulta_vacia_devuelve_none():
    assert emparejar_nombre("", ["Cardiología"]) is None


def test_formatear_citas_vacio():
    assert formatear_citas([]) == "No tienes citas activas."


# ---------------------------------------------------------------------------
# Acciones de solo lectura (con base de datos)
# ---------------------------------------------------------------------------

def _crear_cita(paciente_id, medico_id, especialidad, inicio, estado):
    return CitaORM(
        id=uuid.uuid4(),
        paciente_id=paciente_id,
        medico_id=medico_id,
        especialidad=especialidad,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado,
        motivo="",
        creada_en=AHORA,
    )


@pytest.fixture
def paciente(db):
    p = PacienteORM(
        run_usuario=PACIENTE_RUN,
        nombre="Ana Soto",
        correo="ana@ejemplo.cl",
        telefono=56900000000,
    )
    db.add(p)
    db.commit()
    return p


def test_consultar_mis_citas_lista_solo_las_activas(db, paciente):
    futuro = AHORA + timedelta(days=3)
    db.add(_crear_cita(PACIENTE_RUN, 222, "Cardiología", futuro, EstadoCita.CONFIRMADA))
    db.add(_crear_cita(PACIENTE_RUN, 222, "Pediatría", futuro, EstadoCita.CANCELADA))
    db.commit()

    intencion = IntencionAsistente(accion=AccionAsistente.CONSULTAR_MIS_CITAS)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert "Cardiología" in texto
    assert "Pediatría" not in texto  # la cancelada no aparece


def test_consultar_mis_citas_sin_citas(db, paciente):
    intencion = IntencionAsistente(accion=AccionAsistente.CONSULTAR_MIS_CITAS)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert texto == "No tienes citas activas."


def test_consultar_disponibilidad_sin_especialidad_pide_aclaracion(db):
    intencion = IntencionAsistente(accion=AccionAsistente.CONSULTAR_DISPONIBILIDAD)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert "especialidad" in texto.lower()


def test_consultar_disponibilidad_especialidad_inexistente(db):
    intencion = IntencionAsistente(
        accion=AccionAsistente.CONSULTAR_DISPONIBILIDAD,
        especialidad="oftalmología",
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert "No encontré" in texto


def test_consultar_disponibilidad_sin_agenda_no_ofrece_horas(db):
    especialidad = EspecialidadORM(nombre="Cardiología")
    db.add(especialidad)
    db.flush()
    db.add(
        MedicoORM(
            run_usuario=222222222,
            nombre="Dr. Pérez",
            correo="perez@ejemplo.cl",
            telefono=56911111111,
            especialidad_id=especialidad.id,
        )
    )
    db.commit()

    intencion = IntencionAsistente(
        accion=AccionAsistente.CONSULTAR_DISPONIBILIDAD,
        especialidad="cardio",  # empareja por contención
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert "No hay horas de Cardiología" in texto


# ---------------------------------------------------------------------------
# Acciones que modifican datos
# ---------------------------------------------------------------------------

def _seed_medico_con_agenda(db, especialidad_nombre, dia_semana):
    esp = EspecialidadORM(nombre=especialidad_nombre)
    db.add(esp)
    db.flush()
    db.add(
        MedicoORM(
            run_usuario=MEDICO_RUN,
            nombre="Dr. Pérez",
            correo="perez@ejemplo.cl",
            telefono=56911111111,
            especialidad_id=esp.id,
        )
    )
    db.flush()
    agenda = AgendaORM(medico_run=MEDICO_RUN, duracion_slot_minutos=30)
    db.add(agenda)
    db.flush()
    db.add(
        BloqueHorarioORM(
            agenda_id=agenda.id,
            dia_semana=dia_semana,
            hora_inicio=time(9, 0),
            hora_fin=time(13, 0),
        )
    )
    db.commit()
    return esp


def test_agendar_crea_la_cita(db, paciente):
    slot = datetime(2026, 7, 6, 10, 0)  # lunes dentro del horario 09–13
    _seed_medico_con_agenda(db, "Cardiología", slot.weekday())
    ahora = slot - timedelta(days=5)

    intencion = IntencionAsistente(
        accion=AccionAsistente.AGENDAR, especialidad="cardio", fecha_hora=slot
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=ahora)

    assert "agendé" in texto.lower()
    citas = RepositorioCitas(db).listar_de_paciente(PACIENTE_RUN)
    assert len(citas) == 1
    assert citas[0].estado is EstadoCita.PENDIENTE


def test_agendar_sin_especialidad_pide_dato(db, paciente):
    intencion = IntencionAsistente(accion=AccionAsistente.AGENDAR)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "especialidad" in texto.lower()


def test_agendar_sin_fecha_pide_dato(db, paciente):
    intencion = IntencionAsistente(accion=AccionAsistente.AGENDAR, especialidad="cardio")
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "fecha y hora" in texto.lower()


def test_agendar_horario_no_disponible_ofrece_alternativas(db, paciente):
    slot = datetime(2026, 7, 6, 10, 0)  # lunes con agenda
    _seed_medico_con_agenda(db, "Cardiología", slot.weekday())
    # Pide un martes (sin bloque horario): no hay ese horario exacto.
    pedido = datetime(2026, 7, 7, 10, 0)
    ahora = slot - timedelta(days=5)

    intencion = IntencionAsistente(
        accion=AccionAsistente.AGENDAR, especialidad="cardio", fecha_hora=pedido
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=ahora)

    assert "No hay horas de Cardiología" in texto


def test_cancelar_una_cita(db, paciente):
    futuro = datetime(2026, 7, 6, 10, 0)
    cita = _crear_cita(PACIENTE_RUN, MEDICO_RUN, "Cardiología", futuro, EstadoCita.CONFIRMADA)
    db.add(cita)
    db.commit()

    intencion = IntencionAsistente(
        accion=AccionAsistente.CANCELAR, especialidad="cardiología"
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert "Cancelé" in texto
    db.refresh(cita)
    assert cita.estado is EstadoCita.CANCELADA


def test_cancelar_sin_citas_avisa(db, paciente):
    intencion = IntencionAsistente(accion=AccionAsistente.CANCELAR)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "No encontré" in texto


def test_cancelar_con_varias_pide_especificar(db, paciente):
    f1 = datetime(2026, 7, 6, 10, 0)
    f2 = datetime(2026, 7, 8, 11, 0)
    db.add(_crear_cita(PACIENTE_RUN, MEDICO_RUN, "Cardiología", f1, EstadoCita.CONFIRMADA))
    db.add(_crear_cita(PACIENTE_RUN, 333, "Pediatría", f2, EstadoCita.CONFIRMADA))
    db.commit()

    intencion = IntencionAsistente(accion=AccionAsistente.CANCELAR)  # sin especialidad
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "varias citas" in texto


def test_reagendar_mueve_la_cita(db, paciente):
    original = datetime(2026, 7, 6, 10, 0)
    nueva = datetime(2026, 7, 8, 11, 0)
    cita = _crear_cita(PACIENTE_RUN, MEDICO_RUN, "Cardiología", original, EstadoCita.CONFIRMADA)
    db.add(cita)
    db.commit()
    ahora = datetime(2026, 6, 30, 9, 0)

    intencion = IntencionAsistente(
        accion=AccionAsistente.REAGENDAR, especialidad="cardio", nueva_fecha_hora=nueva
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=ahora)

    assert "Reagendé" in texto
    db.refresh(cita)
    assert cita.estado is EstadoCita.REAGENDADA


def test_reagendar_sin_nueva_hora_pide_dato(db, paciente):
    intencion = IntencionAsistente(accion=AccionAsistente.REAGENDAR)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "nueva fecha" in texto.lower()


def test_inscribir_en_lista_de_espera(db, paciente):
    esp = EspecialidadORM(nombre="Cardiología")
    db.add(esp)
    db.flush()
    db.add(ListaEsperaORM(especialidad_id=esp.id, clinica_rut="1-9"))
    db.commit()

    intencion = IntencionAsistente(
        accion=AccionAsistente.INSCRIBIR_ESPERA, especialidad="cardio"
    )
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "inscribí" in texto.lower()


def test_inscribir_dos_veces_avisa(db, paciente):
    esp = EspecialidadORM(nombre="Cardiología")
    db.add(esp)
    db.flush()
    db.add(ListaEsperaORM(especialidad_id=esp.id, clinica_rut="1-9"))
    db.commit()

    intencion = IntencionAsistente(
        accion=AccionAsistente.INSCRIBIR_ESPERA, especialidad="cardio"
    )
    despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)
    assert "Ya estás inscrito" in texto
