"""Tests del despachador: helpers puros y acciones de solo lectura."""

import uuid
from datetime import datetime, timedelta

import pytest

from app.backend.ai.despachador import (
    despachar,
    emparejar_nombre,
    formatear_citas,
)
from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.domain.enums import EstadoCita
from app.backend.models.citas import CitaORM
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import MedicoORM, PacienteORM

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


def test_accion_que_muta_responde_no_disponible_todavia(db):
    intencion = IntencionAsistente(accion=AccionAsistente.AGENDAR, especialidad="x")
    texto = despachar(db, PACIENTE_RUN, intencion, ahora=AHORA)

    assert "todavía no está disponible" in texto
