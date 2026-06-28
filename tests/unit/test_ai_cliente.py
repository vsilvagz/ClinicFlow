"""Tests de las piezas puras del cliente del asistente (sin llamadas de red)."""

from datetime import datetime

from app.backend.ai.cliente import construir_mensajes, parsear_intencion
from app.backend.ai.intenciones import AccionAsistente

AHORA = datetime(2026, 6, 27, 10, 0)  # un sábado


def test_construir_mensajes_incluye_sistema_contexto_y_usuario():
    mensajes = construir_mensajes("quiero una hora", AHORA)

    assert [m["role"] for m in mensajes] == ["system", "system", "user"]
    assert mensajes[-1]["content"] == "quiero una hora"
    # El contexto temporal expone la fecha y el día de la semana al modelo.
    assert "2026-06-27" in mensajes[1]["content"]
    assert "sábado" in mensajes[1]["content"]


def test_construir_mensajes_lista_las_acciones_validas():
    sistema = construir_mensajes("hola", AHORA)[0]["content"]
    for accion in AccionAsistente:
        assert accion.value in sistema


def test_construir_mensajes_intercala_el_historial():
    historial = [("usuario", "quiero cardiología"), ("asistente", "¿para qué fecha?")]
    mensajes = construir_mensajes("el lunes a las 10", AHORA, historial)

    # Tras los dos system van los turnos previos (traducidos a roles de la API)
    # y, al final, el mensaje actual.
    assert [m["role"] for m in mensajes] == [
        "system", "system", "user", "assistant", "user",
    ]
    assert mensajes[2]["content"] == "quiero cardiología"
    assert mensajes[3]["content"] == "¿para qué fecha?"
    assert mensajes[-1]["content"] == "el lunes a las 10"


def test_parsear_intencion_json_valido():
    crudo = '{"accion": "cancelar", "respuesta": "Cancelo tu cita."}'
    intencion = parsear_intencion(crudo)

    assert intencion.accion is AccionAsistente.CANCELAR
    assert intencion.respuesta == "Cancelo tu cita."


def test_parsear_intencion_tolera_bloque_de_codigo():
    crudo = '```json\n{"accion": "consultar_mis_citas"}\n```'
    intencion = parsear_intencion(crudo)

    assert intencion.accion is AccionAsistente.CONSULTAR_MIS_CITAS


def test_parsear_intencion_basura_devuelve_desconocida():
    intencion = parsear_intencion("esto no es json")

    assert intencion.accion is AccionAsistente.DESCONOCIDA
    assert intencion.respuesta  # da un mensaje al paciente


def test_parsear_intencion_accion_invalida_devuelve_desconocida():
    intencion = parsear_intencion('{"accion": "teletransportar"}')

    assert intencion.accion is AccionAsistente.DESCONOCIDA
