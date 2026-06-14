"""Tests de las reglas de negocio de las citas."""

from datetime import datetime, timedelta, timezone

import pytest

from app.backend.domain.citas import Cita, ESTADOS_ACTIVOS
from app.backend.domain.enums import EstadoCita
from app.backend.domain.errores import (
    CitaEnPasadoError,
    ConflictoDeAgenda,
    TransicionEstadoInvalida,
)

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

TZ = timezone.utc
AHORA = datetime(2026, 6, 13, 10, 0, tzinfo=TZ)
MANANA = AHORA + timedelta(days=1)

# RUNs de prueba (int), consistente con RUN_usuario en usuarios.py
PACIENTE_RUN = 11111111
MEDICO_RUN   = 22222222


def _cita(
    inicio: datetime = MANANA,
    duracion: int = 30,
    paciente_id: int = PACIENTE_RUN,
    medico_id: int = MEDICO_RUN,
) -> Cita:
    return Cita.crear(
        paciente_id=paciente_id,
        medico_id=medico_id,
        especialidad="Cardiología",
        inicio=inicio,
        duracion_minutos=duracion,
        motivo="Control anual",
        ahora=AHORA,
    )


# ---------------------------------------------------------------------------
# Creación
# ---------------------------------------------------------------------------


class TestCrearCita:
    def test_cita_valida_queda_en_pendiente(self):
        cita = _cita()
        assert cita.estado == EstadoCita.PENDIENTE

    def test_fin_calculado_correctamente(self):
        cita = _cita(duracion=45)
        assert cita.fin == cita.inicio + timedelta(minutes=45)

    def test_duracion_minutos_property(self):
        cita = _cita(duracion=60)
        assert cita.duracion_minutos == 60

    def test_cita_en_pasado_lanza_error(self):
        ayer = AHORA - timedelta(days=1)
        with pytest.raises(CitaEnPasadoError):
            _cita(inicio=ayer)

    def test_cita_en_el_mismo_instante_lanza_error(self):
        with pytest.raises(CitaEnPasadoError):
            _cita(inicio=AHORA)

    def test_duracion_cero_lanza_value_error(self):
        with pytest.raises(ValueError):
            _cita(duracion=0)

    def test_duracion_negativa_lanza_value_error(self):
        with pytest.raises(ValueError):
            _cita(duracion=-10)

    def test_ids_son_unicos(self):
        a = _cita()
        b = _cita()
        assert a.id != b.id


# ---------------------------------------------------------------------------
# Transiciones de estado
# ---------------------------------------------------------------------------


class TestTransicionesEstado:
    def test_confirmar_desde_pendiente(self):
        cita = _cita()
        cita.confirmar()
        assert cita.estado == EstadoCita.CONFIRMADA

    def test_cancelar_desde_pendiente(self):
        cita = _cita()
        cita.cancelar()
        assert cita.estado == EstadoCita.CANCELADA

    def test_cancelar_desde_confirmada(self):
        cita = _cita()
        cita.confirmar()
        cita.cancelar()
        assert cita.estado == EstadoCita.CANCELADA

    def test_completar_desde_confirmada(self):
        cita = _cita()
        cita.confirmar()
        cita.completar()
        assert cita.estado == EstadoCita.COMPLETADA

    def test_no_asistio_desde_confirmada(self):
        cita = _cita()
        cita.confirmar()
        cita.marcar_no_asistio()
        assert cita.estado == EstadoCita.NO_ASISTIO

    def test_confirmar_desde_cancelada_lanza_error(self):
        cita = _cita()
        cita.cancelar()
        with pytest.raises(TransicionEstadoInvalida):
            cita.confirmar()

    def test_completar_desde_pendiente_lanza_error(self):
        cita = _cita()
        with pytest.raises(TransicionEstadoInvalida):
            cita.completar()

    def test_completar_desde_completada_lanza_error(self):
        cita = _cita()
        cita.confirmar()
        cita.completar()
        with pytest.raises(TransicionEstadoInvalida):
            cita.completar()

    def test_cancelar_desde_completada_lanza_error(self):
        cita = _cita()
        cita.confirmar()
        cita.completar()
        with pytest.raises(TransicionEstadoInvalida):
            cita.cancelar()

    def test_no_asistio_desde_pendiente_lanza_error(self):
        cita = _cita()
        with pytest.raises(TransicionEstadoInvalida):
            cita.marcar_no_asistio()


# ---------------------------------------------------------------------------
# Reagendamiento
# ---------------------------------------------------------------------------


class TestReagendar:
    def test_reagendar_desde_pendiente_crea_nueva_cita(self):
        cita = _cita()
        nueva_inicio = MANANA + timedelta(days=1)
        nueva = cita.reagendar(nueva_inicio, ahora=AHORA)

        assert cita.estado == EstadoCita.REAGENDADA
        assert nueva.estado == EstadoCita.PENDIENTE
        assert nueva.inicio == nueva_inicio

    def test_reagendar_desde_confirmada(self):
        cita = _cita()
        cita.confirmar()
        nueva = cita.reagendar(MANANA + timedelta(days=2), ahora=AHORA)
        assert cita.estado == EstadoCita.REAGENDADA
        assert nueva.estado == EstadoCita.PENDIENTE

    def test_reagendar_vincula_citas(self):
        cita = _cita()
        nueva = cita.reagendar(MANANA + timedelta(days=1), ahora=AHORA)
        assert nueva.reagendada_desde_id == cita.id
        assert cita.reagendada_hacia_id == nueva.id

    def test_reagendar_hereda_paciente_y_medico(self):
        pid = 12345678   # RUN del paciente de prueba
        mid = 87654321   # RUN del médico de prueba
        cita = _cita(paciente_id=pid, medico_id=mid)
        nueva = cita.reagendar(MANANA + timedelta(days=1), ahora=AHORA)
        assert nueva.paciente_id == pid
        assert nueva.medico_id == mid

    def test_reagendar_desde_cancelada_lanza_error(self):
        cita = _cita()
        cita.cancelar()
        with pytest.raises(TransicionEstadoInvalida):
            cita.reagendar(MANANA + timedelta(days=1), ahora=AHORA)

    def test_reagendar_al_pasado_lanza_error(self):
        cita = _cita()
        with pytest.raises(CitaEnPasadoError):
            cita.reagendar(AHORA - timedelta(hours=1), ahora=AHORA)


# ---------------------------------------------------------------------------
# Detección de solapamiento
# ---------------------------------------------------------------------------


class TestSolapamiento:
    def _par_medico(self, inicio_a: datetime, inicio_b: datetime):
        # Mismo médico (mismo RUN), distintos pacientes
        mid = 33333333
        a = Cita.crear(11111111, mid, "Neurología", inicio_a, 60, ahora=AHORA)
        b = Cita.crear(22222222, mid, "Neurología", inicio_b, 60, ahora=AHORA)
        return a, b

    def test_citas_consecutivas_no_se_solapan(self):
        a, b = self._par_medico(MANANA, MANANA + timedelta(hours=1))
        assert not a.se_solapa_con(b)

    def test_citas_superpuestas_se_solapan(self):
        a, b = self._par_medico(MANANA, MANANA + timedelta(minutes=30))
        assert a.se_solapa_con(b)

    def test_cita_dentro_de_otra_se_solapa(self):
        a, b = self._par_medico(MANANA, MANANA + timedelta(minutes=10))
        assert a.se_solapa_con(b)

    def test_distintos_medicos_no_se_solapan(self):
        # Médicos distintos (RUNs distintos): no hay conflicto aunque coincidan horas
        a = Cita.crear(11111111, 44444444, "Cardiología", MANANA, 60, ahora=AHORA)
        b = Cita.crear(22222222, 55555555, "Cardiología", MANANA, 60, ahora=AHORA)
        assert not a.se_solapa_con(b)

    def test_cita_cancelada_no_genera_conflicto(self):
        mid = 33333333
        a = Cita.crear(11111111, mid, "Pediatría", MANANA, 60, ahora=AHORA)
        b = Cita.crear(22222222, mid, "Pediatría", MANANA, 60, ahora=AHORA)
        b.cancelar()
        assert not a.se_solapa_con(b)

    def test_validar_no_solapa_lanza_error(self):
        mid = 33333333
        existente = Cita.crear(11111111, mid, "Pediatría", MANANA, 60, ahora=AHORA)
        nueva = Cita.crear(22222222, mid, "Pediatría", MANANA + timedelta(minutes=30), 60, ahora=AHORA)
        with pytest.raises(ConflictoDeAgenda):
            nueva.validar_no_solapa([existente])

    def test_validar_no_solapa_no_lanza_si_no_hay_conflicto(self):
        mid = 33333333
        existente = Cita.crear(11111111, mid, "Pediatría", MANANA, 60, ahora=AHORA)
        nueva = Cita.crear(22222222, mid, "Pediatría", MANANA + timedelta(hours=1), 30, ahora=AHORA)
        nueva.validar_no_solapa([existente])  # no debe lanzar


# ---------------------------------------------------------------------------
# Propiedades
# ---------------------------------------------------------------------------


class TestPropiedades:
    def test_esta_activa_en_pendiente(self):
        cita = _cita()
        assert cita.esta_activa is True

    def test_esta_activa_en_confirmada(self):
        cita = _cita()
        cita.confirmar()
        assert cita.esta_activa is True

    def test_no_esta_activa_en_cancelada(self):
        cita = _cita()
        cita.cancelar()
        assert cita.esta_activa is False

    def test_no_esta_activa_en_completada(self):
        cita = _cita()
        cita.confirmar()
        cita.completar()
        assert cita.esta_activa is False

    def test_estados_activos_constante(self):
        assert EstadoCita.PENDIENTE in ESTADOS_ACTIVOS
        assert EstadoCita.CONFIRMADA in ESTADOS_ACTIVOS
        assert EstadoCita.CANCELADA not in ESTADOS_ACTIVOS
