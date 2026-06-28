"""Tests del flujo de gestión de citas para la recepcionista."""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from app.backend.api.deps import COOKIE_SESION
from app.backend.core.database import get_db
from app.backend.core.security import crear_token
from app.backend.domain.enums import EstadoCita
from app.backend.main import app
from app.backend.models.citas import CitaORM
from app.backend.models.usuarios import MedicoORM, PacienteORM, RecepcionistaORM
from fastapi.testclient import TestClient

RECEPCION_RUN = 100000000
PACIENTE_RUN = 111111111
MEDICO_RUN = 222222222


@pytest.fixture
def cliente(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _seed_personas(db):
    db.add(RecepcionistaORM(run_usuario=RECEPCION_RUN, nombre="Rita", correo="r@e.cl", telefono=1))
    db.add(PacienteORM(run_usuario=PACIENTE_RUN, nombre="Ana Soto", correo="a@e.cl", telefono=2))
    db.add(MedicoORM(run_usuario=MEDICO_RUN, nombre="Dr. Pérez", correo="d@e.cl", telefono=3))
    db.commit()


def _seed_cita(db, estado, inicio=None):
    inicio = inicio or datetime.combine(date.today(), time(10, 0))
    cita = CitaORM(
        id=uuid.uuid4(),
        paciente_id=PACIENTE_RUN,
        medico_id=MEDICO_RUN,
        especialidad="Cardiología",
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado,
        motivo="",
        creada_en=inicio,
    )
    db.add(cita)
    db.commit()
    return cita


def _login_recepcion(cliente):
    cliente.cookies.set(COOKIE_SESION, crear_token(str(RECEPCION_RUN)))


def test_pagina_muestra_botones_de_accion(cliente, db):
    _seed_personas(db)
    cita = _seed_cita(db, EstadoCita.PENDIENTE)
    _login_recepcion(cliente)

    resp = cliente.get("/gestion-citas")

    assert resp.status_code == 200
    # Una cita pendiente debe ofrecer confirmar, reagendar y cancelar.
    assert f"/gestion-citas/{cita.id}/confirmar" in resp.text
    assert f"/gestion-citas/{cita.id}/cancelar" in resp.text


def test_completar_marca_la_cita_como_atendida(cliente, db):
    _seed_personas(db)
    cita = _seed_cita(db, EstadoCita.CONFIRMADA)
    _login_recepcion(cliente)

    resp = cliente.post(
        f"/gestion-citas/{cita.id}/completar",
        data={"fecha": date.today().isoformat()},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert db.get(CitaORM, cita.id).estado is EstadoCita.COMPLETADA


def test_confirmar_cambia_pendiente_a_confirmada(cliente, db):
    _seed_personas(db)
    cita = _seed_cita(db, EstadoCita.PENDIENTE)
    _login_recepcion(cliente)

    cliente.post(
        f"/gestion-citas/{cita.id}/confirmar",
        data={"fecha": date.today().isoformat()},
        follow_redirects=False,
    )

    assert db.get(CitaORM, cita.id).estado is EstadoCita.CONFIRMADA


def test_cita_futura_no_ofrece_asistencia(cliente, db):
    _seed_personas(db)
    futura = datetime.now() + timedelta(days=2)
    cita = _seed_cita(db, EstadoCita.CONFIRMADA, inicio=futura)
    _login_recepcion(cliente)

    resp = cliente.get(f"/gestion-citas?fecha={futura.date().isoformat()}")

    assert resp.status_code == 200
    # No se puede marcar asistencia de algo que aún no ocurre…
    assert f"/gestion-citas/{cita.id}/completar" not in resp.text
    assert f"/gestion-citas/{cita.id}/no-asistio" not in resp.text
    # …pero sí reagendar o cancelar.
    assert f"/gestion-citas/{cita.id}/cancelar" in resp.text


def test_cita_pasada_ofrece_asistencia(cliente, db):
    _seed_personas(db)
    pasada = datetime.now() - timedelta(days=2)
    cita = _seed_cita(db, EstadoCita.CONFIRMADA, inicio=pasada)
    _login_recepcion(cliente)

    resp = cliente.get(f"/gestion-citas?fecha={pasada.date().isoformat()}")

    assert resp.status_code == 200
    assert f"/gestion-citas/{cita.id}/completar" in resp.text
    assert f"/gestion-citas/{cita.id}/no-asistio" in resp.text


def test_completar_solo_lo_puede_un_rol_autorizado(cliente, db):
    _seed_personas(db)
    cita = _seed_cita(db, EstadoCita.CONFIRMADA)
    # Sesión de paciente: no autorizado, debe redirigir sin completar.
    cliente.cookies.set(COOKIE_SESION, crear_token(str(PACIENTE_RUN)))

    resp = cliente.post(
        f"/gestion-citas/{cita.id}/completar",
        data={"fecha": date.today().isoformat()},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal"
    assert db.get(CitaORM, cita.id).estado is EstadoCita.CONFIRMADA