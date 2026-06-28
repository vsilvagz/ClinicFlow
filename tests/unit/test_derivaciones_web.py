"""Tests del flujo web de derivaciones (médico emite, admin solo observa)."""

import pytest
from app.backend.api.deps import COOKIE_SESION
from app.backend.core.database import get_db
from app.backend.core.security import crear_token
from app.backend.main import app
from app.backend.models.derivacion import DerivacionORM
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import AdministradorORM, MedicoORM, PacienteORM
from fastapi.testclient import TestClient
from sqlalchemy import select

MEDICO_RUN = 222222222
PACIENTE_RUN = 111111111
ADMIN_RUN = 999999999


@pytest.fixture
def cliente(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _seed(db):
    db.add(MedicoORM(run_usuario=MEDICO_RUN, nombre="Dr. Pérez", correo="d@e.cl", telefono=1))
    db.add(PacienteORM(run_usuario=PACIENTE_RUN, nombre="Ana Soto", correo="a@e.cl", telefono=2))
    db.add(AdministradorORM(run_usuario=ADMIN_RUN, nombre="Admin", correo="ad@e.cl", telefono=3))
    db.add(EspecialidadORM(nombre="Neurología"))
    db.commit()


def _login(cliente, run):
    cliente.cookies.set(COOKIE_SESION, crear_token(str(run)))


def test_medico_ve_el_formulario_de_derivacion(cliente, db):
    _seed(db)
    _login(cliente, MEDICO_RUN)

    resp = cliente.get("/derivaciones")

    assert resp.status_code == 200
    assert 'action="/derivaciones/nueva"' in resp.text
    assert "Neurología" in resp.text  # opción de especialidad destino


def test_admin_no_ve_el_formulario(cliente, db):
    _seed(db)
    _login(cliente, ADMIN_RUN)

    resp = cliente.get("/derivaciones")

    assert resp.status_code == 200
    assert 'action="/derivaciones/nueva"' not in resp.text


def test_medico_emite_una_derivacion(cliente, db):
    _seed(db)
    _login(cliente, MEDICO_RUN)

    cliente.post(
        "/derivaciones/nueva",
        data={
            "paciente_id": PACIENTE_RUN,
            "especialidad_destino": "Neurología",
            "motivo": "Requiere evaluación",
            "dias_vigencia": 30,
        },
        follow_redirects=False,
    )

    derivaciones = list(db.scalars(select(DerivacionORM)))
    assert len(derivaciones) == 1
    assert derivaciones[0].paciente_id == PACIENTE_RUN
    assert derivaciones[0].especialidad_destino == "Neurología"


def test_paciente_no_puede_emitir(cliente, db):
    _seed(db)
    _login(cliente, PACIENTE_RUN)

    resp = cliente.post(
        "/derivaciones/nueva",
        data={"paciente_id": PACIENTE_RUN, "especialidad_destino": "Neurología"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal"
    assert list(db.scalars(select(DerivacionORM))) == []
