"""Tests del bot de Telegram (lógica síncrona, sin red ni Telegram).

Se ejercita el mapeo chat→paciente y el flujo de mensajes con la base en memoria
del fixture `db`. Como los helpers del bot abren su propia sesión con
`SessionLocal`, la reemplazamos por la sesión del test (misma BD) y neutralizamos
`close()` para poder inspeccionar el resultado después de cada llamada. El modelo
de lenguaje (`interpretar`) se sustituye por una intención fija: probamos el
cableado del bot, no el LLM.
"""

import pytest

from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.bot import interactive_telegram as bot
from app.backend.core.security import hash_password
from app.backend.models.usuarios import AdministradorORM, PacienteORM
from app.backend.repositories.conversacion import RepositorioConversacion
from app.backend.repositories.usuarios import RepositorioUsuarios

CHAT_ID = 987654321
RUN_PACIENTE = 44444444
PASSWORD = "demo1234"


@pytest.fixture
def bot_env(db, monkeypatch):
    """Hace que los helpers del bot usen la sesión del test y no la cierren."""
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(bot, "SessionLocal", lambda: db)
    return db


# Los usuarios se crean vía ORM directo (con hash real de contraseña) para no
# depender del esquema Pydantic con EmailStr: probamos el bot, no la validación
# de correos. `rol` lo fija SQLAlchemy según la subclase (herencia de tabla única).

def _crear_paciente(db, run=RUN_PACIENTE, nombre="Pedro Soto"):
    paciente = PacienteORM(
        run_usuario=run,
        nombre=nombre,
        correo=f"p{run}@example.cl",
        telefono=930000000,
        password_hash=hash_password(PASSWORD),
    )
    db.add(paciente)
    db.commit()
    return paciente


def _crear_administrador(db, run=10000000):
    admin = AdministradorORM(
        run_usuario=run,
        nombre="Admin",
        correo="admin@clinicflow.cl",
        telefono=900000000,
        password_hash=hash_password(PASSWORD),
    )
    db.add(admin)
    db.commit()
    return admin


# ── Vinculación ───────────────────────────────────────────────────────────────

def test_vincular_con_credenciales_correctas_asocia_el_chat(bot_env):
    db = bot_env
    _crear_paciente(db)

    respuesta = bot._vincular(CHAT_ID, [str(RUN_PACIENTE), PASSWORD])

    assert "Pedro Soto" in respuesta
    # El chat quedó efectivamente vinculado a esa cuenta.
    paciente = RepositorioUsuarios(db).obtener_paciente_por_chat(CHAT_ID)
    assert paciente is not None
    assert paciente.run_usuario == RUN_PACIENTE


def test_vincular_con_password_incorrecta_no_vincula(bot_env):
    db = bot_env
    _crear_paciente(db)

    respuesta = bot._vincular(CHAT_ID, [str(RUN_PACIENTE), "clave-mala"])

    assert "incorrect" in respuesta.lower()
    assert RepositorioUsuarios(db).obtener_paciente_por_chat(CHAT_ID) is None


def test_vincular_rechaza_cuentas_que_no_son_paciente(bot_env):
    db = bot_env
    _crear_administrador(db)

    respuesta = bot._vincular(CHAT_ID, ["10000000", PASSWORD])

    assert "paciente" in respuesta.lower()


def test_vincular_sin_argumentos_suficientes_muestra_el_uso(bot_env):
    respuesta = bot._vincular(CHAT_ID, ["44444444"])
    assert respuesta == bot.MENSAJE_USO_VINCULAR


def test_revincular_el_mismo_chat_a_otra_cuenta_libera_la_anterior(bot_env):
    db = bot_env
    _crear_paciente(db, run=RUN_PACIENTE, nombre="Pedro Soto")
    _crear_paciente(db, run=55555555, nombre="Maria Gonzalez")

    bot._vincular(CHAT_ID, [str(RUN_PACIENTE), PASSWORD])
    bot._vincular(CHAT_ID, ["55555555", PASSWORD])

    repo = RepositorioUsuarios(db)
    # El chat ahora apunta a la segunda cuenta y la primera quedó libre.
    assert repo.obtener_paciente_por_chat(CHAT_ID).run_usuario == 55555555
    assert repo.obtener_paciente(RUN_PACIENTE).telegram_chat_id is None


# ── Desvinculación ────────────────────────────────────────────────────────────

def test_desvincular_quita_el_vinculo(bot_env):
    db = bot_env
    _crear_paciente(db)
    bot._vincular(CHAT_ID, [str(RUN_PACIENTE), PASSWORD])

    respuesta = bot._desvincular(CHAT_ID)

    assert "desvinculada" in respuesta.lower()
    assert RepositorioUsuarios(db).obtener_paciente_por_chat(CHAT_ID) is None


def test_desvincular_chat_sin_vinculo_lo_informa(bot_env):
    respuesta = bot._desvincular(CHAT_ID)
    assert "no tenía" in respuesta.lower() or "no tenia" in respuesta.lower()


# ── Flujo de mensajes ─────────────────────────────────────────────────────────

def test_responder_pide_vincular_si_el_chat_no_esta_asociado(bot_env, monkeypatch):
    # interpretar no debería ni llamarse; si lo hace, el test fallaría al no
    # tener LLM, así que lo dejamos explícito con un stub que rompe.
    monkeypatch.setattr(
        bot, "interpretar", lambda *a, **k: pytest.fail("no debe interpretar")
    )
    respuesta = bot._responder(CHAT_ID, "hola")
    assert respuesta == bot.MENSAJE_NO_VINCULADO


def test_responder_ejecuta_la_intencion_y_guarda_el_dialogo(bot_env, monkeypatch):
    db = bot_env
    _crear_paciente(db)
    bot._vincular(CHAT_ID, [str(RUN_PACIENTE), PASSWORD])

    # El LLM se sustituye por una intención fija de consulta de citas.
    monkeypatch.setattr(
        bot,
        "interpretar",
        lambda *a, **k: IntencionAsistente(accion=AccionAsistente.CONSULTAR_MIS_CITAS),
    )

    respuesta = bot._responder(CHAT_ID, "¿qué citas tengo?")

    # El paciente no tiene citas: la respuesta viene del despachador real.
    assert respuesta == "No tienes citas activas."
    # Se registró el diálogo (turno del usuario + turno del asistente).
    turnos = RepositorioConversacion(db).ultimos_de_paciente(RUN_PACIENTE)
    assert len(turnos) == 2
    assert turnos[0].contenido == "¿qué citas tengo?"
    assert turnos[1].contenido == "No tienes citas activas."


def test_construir_bot_sin_token_devuelve_none(monkeypatch):
    monkeypatch.setattr(bot.settings, "telegram_bot_token", "")
    assert bot.construir_bot() is None
