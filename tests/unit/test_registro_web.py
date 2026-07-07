"""Tests del auto-registro de pacientes (formulario público /registro)."""

import pytest
from app.backend.api.deps import COOKIE_SESION
from app.backend.core.database import get_db
from app.backend.main import app
from app.backend.models.usuarios import PacienteORM
from app.backend.services.usuarios_service import autenticar
from fastapi.testclient import TestClient
from sqlalchemy import select

PACIENTE_RUN = 11000001


@pytest.fixture
def cliente(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _datos(**cambios):
    base = {
        "run": "11.000.001",
        "nombre": "Ana Rojas",
        "correo": "ana@correo.cl",
        "telefono": "912345678",
        "password": "clave123",
    }
    base.update(cambios)
    return base


def test_registro_crea_paciente_e_inicia_sesion(cliente, db):
    resp = cliente.post("/registro", data=_datos(), follow_redirects=False)

    # Redirige al portal con la sesión ya abierta (cookie de sesión presente).
    assert resp.status_code == 303
    assert resp.headers["location"] == "/portal"
    assert COOKIE_SESION in resp.cookies

    # El paciente quedó guardado con los datos del formulario.
    paciente = db.get(PacienteORM, PACIENTE_RUN)
    assert paciente is not None
    assert paciente.nombre == "Ana Rojas"
    assert paciente.correo == "ana@correo.cl"
    assert paciente.telefono == 912345678

    # Y puede autenticarse con la contraseña que eligió (quedó hasheada).
    assert autenticar(db, PACIENTE_RUN, "clave123") is not None


def test_rut_duplicado_es_rechazado(cliente, db):
    db.add(PacienteORM(run_usuario=PACIENTE_RUN, nombre="Otro", correo="o@e.cl", telefono=1))
    db.commit()

    resp = cliente.post("/registro", data=_datos(), follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/registro?error=rut_ocupado"


def test_rut_invalido_es_rechazado(cliente, db):
    resp = cliente.post("/registro", data=_datos(run="abc"), follow_redirects=False)

    assert resp.headers["location"] == "/registro?error=rut"
    assert list(db.scalars(select(PacienteORM))) == []


def test_contrasena_corta_es_rechazada(cliente, db):
    resp = cliente.post("/registro", data=_datos(password="12"), follow_redirects=False)

    assert resp.headers["location"] == "/registro?error=datos"
    assert list(db.scalars(select(PacienteORM))) == []


def test_telefono_no_numerico_es_rechazado(cliente, db):
    resp = cliente.post("/registro", data=_datos(telefono="sin numeros"), follow_redirects=False)

    assert resp.headers["location"] == "/registro?error=telefono"
    assert list(db.scalars(select(PacienteORM))) == []
