"""Tests del repositorio de conversación del asistente."""

from app.backend.models.conversacion import ROL_ASISTENTE, ROL_USUARIO
from app.backend.repositories.conversacion import RepositorioConversacion

PACIENTE_RUN = 111111111


def test_agregar_y_recuperar_turnos_en_orden(db):
    repo = RepositorioConversacion(db)
    repo.agregar_turno(PACIENTE_RUN, ROL_USUARIO, "hola")
    repo.agregar_turno(PACIENTE_RUN, ROL_ASISTENTE, "¿en qué te ayudo?")

    turnos = repo.ultimos_de_paciente(PACIENTE_RUN)

    assert [(t.rol, t.contenido) for t in turnos] == [
        (ROL_USUARIO, "hola"),
        (ROL_ASISTENTE, "¿en qué te ayudo?"),
    ]


def test_ultimos_respeta_el_limite_y_mantiene_los_recientes(db):
    repo = RepositorioConversacion(db)
    for i in range(5):
        repo.agregar_turno(PACIENTE_RUN, ROL_USUARIO, f"mensaje {i}")

    turnos = repo.ultimos_de_paciente(PACIENTE_RUN, limite=2)

    # Se queda con los dos más recientes, en orden cronológico.
    assert [t.contenido for t in turnos] == ["mensaje 3", "mensaje 4"]


def test_turnos_se_separan_por_paciente(db):
    repo = RepositorioConversacion(db)
    repo.agregar_turno(PACIENTE_RUN, ROL_USUARIO, "soy 111")
    repo.agregar_turno(222222222, ROL_USUARIO, "soy 222")

    turnos = repo.ultimos_de_paciente(PACIENTE_RUN)

    assert len(turnos) == 1
    assert turnos[0].contenido == "soy 111"
