"""Tests de integración del endpoint web del asistente."""

import pytest
from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.api.deps import COOKIE_SESION
from app.backend.core.database import get_db
from app.backend.core.security import crear_token
from app.backend.main import app
from app.backend.models.conversacion import ROL_ASISTENTE, ROL_USUARIO
from app.backend.models.usuarios import MedicoORM, PacienteORM
from app.backend.repositories.conversacion import RepositorioConversacion
from fastapi.testclient import TestClient

PACIENTE_RUN = 111111111


@pytest.fixture
def cliente(db):
    """TestClient con la sesión de BD de prueba inyectada en lugar de Postgres.

    No se usa como context manager a propósito: así no se ejecuta el `lifespan`
    de la app (que crearía tablas y sembraría datos contra Postgres real).
    """
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _autenticar(cliente, run):
    cliente.cookies.set(COOKIE_SESION, crear_token(str(run)))


def test_mensaje_sin_sesion_devuelve_401(cliente):
    resp = cliente.post("/asistente/mensaje", json={"mensaje": "hola"})
    assert resp.status_code == 401


def test_mensaje_de_no_paciente_devuelve_401(cliente, db):
    db.add(MedicoORM(run_usuario=222, nombre="Dr.", correo="d@e.cl", telefono=56900000000))
    db.commit()
    _autenticar(cliente, 222)

    resp = cliente.post("/asistente/mensaje", json={"mensaje": "hola"})
    assert resp.status_code == 401


def test_mensaje_de_paciente_devuelve_respuesta(cliente, db, monkeypatch):
    db.add(
        PacienteORM(
            run_usuario=PACIENTE_RUN,
            nombre="Ana Soto",
            correo="ana@ejemplo.cl",
            telefono=56900000000,
        )
    )
    db.commit()
    _autenticar(cliente, PACIENTE_RUN)

    # Evitamos la red: forzamos la intención que devolvería el modelo.
    monkeypatch.setattr(
        "app.backend.api.routes.asistente.interpretar",
        lambda mensaje, ahora=None, historial=None: IntencionAsistente(
            accion=AccionAsistente.CONSULTAR_MIS_CITAS
        ),
    )

    resp = cliente.post("/asistente/mensaje", json={"mensaje": "qué citas tengo"})

    assert resp.status_code == 200
    datos = resp.json()
    assert datos["accion"] == "consultar_mis_citas"
    assert "No tienes citas activas" in datos["respuesta"]


def _seed_paciente(db):
    db.add(
        PacienteORM(
            run_usuario=PACIENTE_RUN,
            nombre="Ana Soto",
            correo="ana@ejemplo.cl",
            telefono=56900000000,
        )
    )
    db.commit()


def test_conversacion_persiste_los_dos_turnos(cliente, db, monkeypatch):
    _seed_paciente(db)
    _autenticar(cliente, PACIENTE_RUN)
    monkeypatch.setattr(
        "app.backend.api.routes.asistente.interpretar",
        lambda mensaje, ahora=None, historial=None: IntencionAsistente(
            accion=AccionAsistente.CONSULTAR_MIS_CITAS
        ),
    )

    cliente.post("/asistente/mensaje", json={"mensaje": "hola"})

    turnos = RepositorioConversacion(db).ultimos_de_paciente(PACIENTE_RUN)
    assert [t.rol for t in turnos] == [ROL_USUARIO, ROL_ASISTENTE]
    assert turnos[0].contenido == "hola"


def test_el_segundo_mensaje_recibe_el_historial(cliente, db, monkeypatch):
    _seed_paciente(db)
    _autenticar(cliente, PACIENTE_RUN)

    capturado = {}

    def fake_interpretar(mensaje, ahora=None, historial=None):
        capturado["historial"] = historial
        return IntencionAsistente(accion=AccionAsistente.CONSULTAR_MIS_CITAS)

    monkeypatch.setattr(
        "app.backend.api.routes.asistente.interpretar", fake_interpretar
    )

    cliente.post("/asistente/mensaje", json={"mensaje": "primero"})
    cliente.post("/asistente/mensaje", json={"mensaje": "segundo"})

    # En la segunda llamada el historial trae los dos turnos del primer mensaje.
    assert capturado["historial"][0] == (ROL_USUARIO, "primero")
    assert len(capturado["historial"]) == 2


def test_recargar_la_pagina_reinicia_la_conversacion(cliente, db):
    _seed_paciente(db)
    _autenticar(cliente, PACIENTE_RUN)
    chat = RepositorioConversacion(db)
    chat.agregar_turno(PACIENTE_RUN, ROL_USUARIO, "contexto viejo")

    resp = cliente.get("/asistente")

    assert resp.status_code == 200
    assert chat.ultimos_de_paciente(PACIENTE_RUN) == []
