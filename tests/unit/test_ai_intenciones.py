"""Tests del contrato de salida estructurada del asistente."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.domain.enums import PrioridadEspera


def test_intencion_minima_solo_requiere_accion():
    """Con solo la acción, los demás parámetros quedan en None y respuesta vacía."""
    intencion = IntencionAsistente(accion="consultar_mis_citas")

    assert intencion.accion is AccionAsistente.CONSULTAR_MIS_CITAS
    assert intencion.especialidad is None
    assert intencion.medico is None
    assert intencion.fecha_hora is None
    assert intencion.prioridad is None
    assert intencion.respuesta == ""


def test_intencion_agendar_completa():
    intencion = IntencionAsistente(
        accion="agendar",
        especialidad="cardiología",
        fecha_hora="2026-07-01T15:30:00",
        motivo="dolor de pecho",
        respuesta="Te busco una hora de cardiología.",
    )

    assert intencion.accion is AccionAsistente.AGENDAR
    assert intencion.fecha_hora == datetime(2026, 7, 1, 15, 30)
    assert intencion.motivo == "dolor de pecho"


def test_prioridad_acepta_valor_del_dominio():
    intencion = IntencionAsistente(accion="inscribir_espera", prioridad="urgente")
    assert intencion.prioridad is PrioridadEspera.URGENTE


def test_accion_invalida_es_rechazada():
    with pytest.raises(ValidationError):
        IntencionAsistente(accion="hacer_magia")


def test_fecha_hora_invalida_es_rechazada():
    with pytest.raises(ValidationError):
        IntencionAsistente(accion="agendar", fecha_hora="mañana por la tarde")
