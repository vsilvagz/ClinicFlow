"""Tests de la agenda médica: horarios, bloqueos, suspensiones y citas."""

from datetime import datetime, time, timedelta

import pytest

from app.backend.domain.agenda import Agenda, BloqueHorario, Bloqueo, Suspension
from app.backend.domain.citas import Cita
from app.backend.domain.errores import AgendaSuspendida, ConflictoDeAgenda, HorarioNoDisponible

# ---------------------------------------------------------------------------
# Constantes de prueba
# ---------------------------------------------------------------------------

AHORA = datetime(2026, 6, 13, 10, 0)     # Sábado
MANANA = AHORA + timedelta(days=1)        # Domingo (weekday 6)
DIA_MANANA = MANANA.weekday()             # 6

# Horario de atención para MAÑANA: 08:00 – 18:00
BLOQUE_MANANA = BloqueHorario(
    dia_semana=DIA_MANANA,
    hora_inicio=time(8, 0),
    hora_fin=time(18, 0),
)

P_RUN = 11111111
M_RUN = 22222222


def _cita(inicio: datetime = None, duracion: int = 30) -> Cita:
    return Cita.crear(
        paciente_id=P_RUN,
        medico_id=M_RUN,
        especialidad="Cardiología",
        inicio=inicio or MANANA.replace(hour=9),
        duracion_minutos=duracion,
        ahora=AHORA,
    )


def _agenda_con_horario() -> Agenda:
    ag = Agenda()
    ag.agregar_horario(BLOQUE_MANANA)
    return ag


# ---------------------------------------------------------------------------
# BloqueHorario
# ---------------------------------------------------------------------------


class TestBloqueHorario:
    def test_cubre_inicio_en_horario(self):
        inicio = MANANA.replace(hour=9, minute=0)
        fin = inicio + timedelta(minutes=30)
        assert BLOQUE_MANANA.cubre(inicio, fin)

    def test_no_cubre_dia_equivocado(self):
        otro_dia = MANANA - timedelta(days=1)  # Sábado
        inicio = otro_dia.replace(hour=9)
        fin = inicio + timedelta(minutes=30)
        assert not BLOQUE_MANANA.cubre(inicio, fin)

    def test_no_cubre_fuera_de_horario(self):
        inicio = MANANA.replace(hour=7, minute=0)   # Antes de las 08:00
        fin = inicio + timedelta(minutes=30)
        assert not BLOQUE_MANANA.cubre(inicio, fin)

    def test_no_cubre_fin_despues_del_cierre(self):
        inicio = MANANA.replace(hour=17, minute=45)  # Fin a las 18:15 > 18:00
        fin = inicio + timedelta(minutes=30)
        assert not BLOQUE_MANANA.cubre(inicio, fin)


# ---------------------------------------------------------------------------
# Bloqueo
# ---------------------------------------------------------------------------


class TestBloqueo:
    def _bloqueo(self) -> Bloqueo:
        inicio = MANANA.replace(hour=10)
        return Bloqueo(inicio=inicio, fin=inicio + timedelta(hours=2))

    def test_se_solapa_intervalo_dentro(self):
        b = self._bloqueo()
        assert b.se_solapa_con(b.inicio + timedelta(minutes=30), b.inicio + timedelta(minutes=60))

    def test_se_solapa_intervalo_superpuesto(self):
        b = self._bloqueo()
        assert b.se_solapa_con(b.inicio - timedelta(minutes=30), b.inicio + timedelta(minutes=30))

    def test_no_se_solapa_antes(self):
        b = self._bloqueo()
        fin = b.inicio
        assert not b.se_solapa_con(fin - timedelta(hours=2), fin)

    def test_no_se_solapa_despues(self):
        b = self._bloqueo()
        assert not b.se_solapa_con(b.fin, b.fin + timedelta(hours=1))


# ---------------------------------------------------------------------------
# Suspension
# ---------------------------------------------------------------------------


class TestSuspension:
    def test_se_solapa_con_cita_dentro_del_periodo(self):
        s = Suspension(inicio=MANANA.replace(hour=8), fin=MANANA.replace(hour=18))
        assert s.se_solapa_con(MANANA.replace(hour=9), MANANA.replace(hour=9, minute=30))

    def test_no_se_solapa_fuera_del_periodo(self):
        s = Suspension(inicio=MANANA.replace(hour=8), fin=MANANA.replace(hour=12))
        assert not s.se_solapa_con(MANANA.replace(hour=14), MANANA.replace(hour=15))


# ---------------------------------------------------------------------------
# Agenda — configuración
# ---------------------------------------------------------------------------


class TestAgendaConfiguracion:
    def test_duracion_slot_invalida_lanza_error(self):
        with pytest.raises(ValueError):
            Agenda(duracion_slot_minutos=0)

    def test_duracion_slot_negativa_lanza_error(self):
        with pytest.raises(ValueError):
            Agenda(duracion_slot_minutos=-10)

    def test_bloquear_devuelve_bloqueo(self):
        ag = _agenda_con_horario()
        b = ag.bloquear(MANANA.replace(hour=10), MANANA.replace(hour=11), "Reunión")
        assert isinstance(b, Bloqueo)
        assert b.motivo == "Reunión"


# ---------------------------------------------------------------------------
# Agenda — agregar_cita y validaciones
# ---------------------------------------------------------------------------


class TestAgendaAgregarCita:
    def test_agrega_cita_valida(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=9))
        ag.agregar_cita(cita)
        assert cita in ag.citas_activas()

    def test_rechaza_cita_fuera_de_horario(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=7))
        with pytest.raises(HorarioNoDisponible):
            ag.agregar_cita(cita)

    def test_rechaza_cita_en_suspension(self):
        ag = _agenda_con_horario()
        inicio_s = MANANA.replace(hour=8)
        ag.suspender(inicio_s, MANANA.replace(hour=18), "Paro")
        cita = _cita(inicio=MANANA.replace(hour=9))
        with pytest.raises(AgendaSuspendida):
            ag.agregar_cita(cita)

    def test_rechaza_cita_en_bloqueo(self):
        ag = _agenda_con_horario()
        ag.bloquear(MANANA.replace(hour=9), MANANA.replace(hour=10))
        cita = _cita(inicio=MANANA.replace(hour=9))
        with pytest.raises(ConflictoDeAgenda):
            ag.agregar_cita(cita)

    def test_rechaza_cita_solapada(self):
        ag = _agenda_con_horario()
        cita1 = _cita(inicio=MANANA.replace(hour=9), duracion=60)
        ag.agregar_cita(cita1)
        cita2 = _cita(inicio=MANANA.replace(hour=9, minute=30), duracion=30)
        with pytest.raises(ConflictoDeAgenda):
            ag.agregar_cita(cita2)

    def test_permite_citas_consecutivas(self):
        ag = _agenda_con_horario()
        cita1 = _cita(inicio=MANANA.replace(hour=9), duracion=30)
        cita2 = _cita(inicio=MANANA.replace(hour=9, minute=30), duracion=30)
        ag.agregar_cita(cita1)
        ag.agregar_cita(cita2)  # no debe lanzar

    def test_rechaza_si_supera_capacidad_diaria(self):
        ag = Agenda(capacidad_maxima_dia=1)
        ag.agregar_horario(BLOQUE_MANANA)
        cita1 = _cita(inicio=MANANA.replace(hour=9), duracion=30)
        cita2 = _cita(inicio=MANANA.replace(hour=10), duracion=30)
        ag.agregar_cita(cita1)
        with pytest.raises(ConflictoDeAgenda):
            ag.agregar_cita(cita2)


# ---------------------------------------------------------------------------
# Agenda — suspender cancela citas activas
# ---------------------------------------------------------------------------


class TestAgendaSuspender:
    def test_suspension_cancela_citas_activas_en_el_periodo(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=9))
        ag.agregar_cita(cita)

        _, canceladas = ag.suspender(
            MANANA.replace(hour=8), MANANA.replace(hour=18), "Paro"
        )

        assert cita in canceladas
        assert not cita.esta_activa

    def test_suspension_no_cancela_citas_fuera_del_periodo(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=9))
        ag.agregar_cita(cita)

        # Suspensión que NO incluye las 09:00
        _, canceladas = ag.suspender(
            MANANA.replace(hour=14), MANANA.replace(hour=18), "Tarde"
        )

        assert cita not in canceladas
        assert cita.esta_activa

    def test_suspension_no_cancela_citas_ya_canceladas(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=9))
        ag.agregar_cita(cita)
        cita.cancelar()

        _, canceladas = ag.suspender(
            MANANA.replace(hour=8), MANANA.replace(hour=18), "Paro"
        )

        assert cita not in canceladas


# ---------------------------------------------------------------------------
# Agenda — disponibilidad y slots
# ---------------------------------------------------------------------------


class TestAgendaDisponibilidad:
    def test_slot_libre_esta_disponible(self):
        ag = _agenda_con_horario()
        assert ag.esta_disponible(MANANA.replace(hour=9))

    def test_slot_ocupado_no_esta_disponible(self):
        ag = _agenda_con_horario()
        inicio = MANANA.replace(hour=9)
        ag.agregar_cita(_cita(inicio=inicio, duracion=30))
        assert not ag.esta_disponible(inicio)

    def test_slot_fuera_de_horario_no_disponible(self):
        ag = _agenda_con_horario()
        assert not ag.esta_disponible(MANANA.replace(hour=7))

    def test_slots_disponibles_devuelve_lista(self):
        ag = _agenda_con_horario()
        slots = ag.slots_disponibles(MANANA.date())
        assert len(slots) > 0
        # Todos deben estar dentro del horario 08:00-18:00
        for s in slots:
            assert s.time() >= time(8, 0)

    def test_slots_disponibles_excluye_ocupados(self):
        ag = _agenda_con_horario()
        inicio = MANANA.replace(hour=9)
        ag.agregar_cita(_cita(inicio=inicio, duracion=30))
        slots = ag.slots_disponibles(MANANA.date())
        assert inicio not in slots

    def test_citas_del_dia_filtra_por_fecha(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=9))
        ag.agregar_cita(cita)
        assert cita in ag.citas_del_dia(MANANA.date())

    def test_citas_del_dia_no_incluye_otro_dia(self):
        ag = _agenda_con_horario()
        cita = _cita(inicio=MANANA.replace(hour=9))
        ag.agregar_cita(cita)
        otro_dia = (MANANA + timedelta(days=7)).date()
        assert cita not in ag.citas_del_dia(otro_dia)
