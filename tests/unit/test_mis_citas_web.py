"""Test de regresión: el paciente ve las acciones sobre sus citas activas."""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from app.backend.api.deps import COOKIE_SESION
from app.backend.core.database import get_db
from app.backend.core.security import crear_token
from app.backend.domain.enums import EstadoCita
from app.backend.main import app
from app.backend.models.citas import CitaORM
from app.backend.models.usuarios import MedicoORM, PacienteORM
from fastapi.testclient import TestClient

PACIENTE_RUN = 111111111
MEDICO_RUN = 222222222


@pytest.fixture
def cliente(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_cita_activa_ofrece_cancelar_y_reagendar(cliente, db):
    db.add(PacienteORM(run_usuario=PACIENTE_RUN, nombre="Ana", correo="a@e.cl", telefono=1))
    db.add(MedicoORM(run_usuario=MEDICO_RUN, nombre="Dr. Pérez", correo="d@e.cl", telefono=2))
    inicio = datetime.combine(date.today() + timedelta(days=1), time(10, 0))
    cita = CitaORM(
        id=uuid.uuid4(),
        paciente_id=PACIENTE_RUN,
        medico_id=MEDICO_RUN,
        especialidad="Cardiología",
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=EstadoCita.CONFIRMADA,
        motivo="",
        creada_en=inicio,
    )
    db.add(cita)
    db.commit()

    cliente.cookies.set(COOKIE_SESION, crear_token(str(PACIENTE_RUN)))
    resp = cliente.get("/mis-citas")

    assert resp.status_code == 200
    assert f"/mis-citas/{cita.id}/cancelar" in resp.text
    assert f"/mis-citas/{cita.id}/reagendar" in resp.text
