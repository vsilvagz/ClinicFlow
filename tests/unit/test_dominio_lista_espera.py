"""Tests de la lista de espera (enunciado 3.1.3)."""

from datetime import datetime, time, timedelta

import pytest

from app.backend.domain.agenda import Agenda, BloqueHorario
from app.backend.domain.clinica import Clinica
from app.backend.domain.enums import PrioridadEspera
from app.backend.domain.especialidades import Especialidad
from app.backend.domain.lista_espera import Lista_de_Espera
from app.backend.domain.usuarios import Medico, Paciente

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Usamos un slot bien en el futuro para que Cita.crear() no lo rechace
# comparando contra datetime.now() al llamar asignar_hora_disponible.
SLOT_FUTURO = datetime.now() + timedelta(days=60)
DIA_SLOT = SLOT_FUTURO.weekday()

ESPECIALIDAD_CARDIO = Especialidad("Cardiología")


def _clinica() -> Clinica:
    return Clinica("12345678-9", "Clínica Test", "Calle Falsa 123")


def _medico(run: int = 22222222) -> Medico:
    m = Medico(run, f"Dr. Test {run}", f"doc{run}@test.cl", 912345678, ESPECIALIDAD_CARDIO)
    # Horario todos los días (para que cualquier SLOT_FUTURO sea válido)
    for dia in range(7):
        m.agenda.agregar_horario(BloqueHorario(dia, time(8, 0), time(18, 0)))
    return m


def _paciente(run: int) -> Paciente:
    return Paciente(run, f"Paciente {run}", f"p{run}@test.cl", 912345678)


def _lista() -> Lista_de_Espera:
    return Lista_de_Espera(ESPECIALIDAD_CARDIO, _clinica())


# ---------------------------------------------------------------------------
# Inscripción
# ---------------------------------------------------------------------------


class TestInscripcion:
    def test_agregar_paciente_devuelve_true(self):
        lista = _lista()
        p = _paciente(11111111)
        assert lista.agregar_paciente_en_lista(p) is True

    def test_agregar_duplicado_devuelve_false(self):
        lista = _lista()
        p = _paciente(11111111)
        lista.agregar_paciente_en_lista(p)
        assert lista.agregar_paciente_en_lista(p) is False

    def test_inscripcion_usa_datetime_now_si_no_se_entrega_fecha(self):
        lista = _lista()
        p = _paciente(11111111)
        lista.agregar_paciente_en_lista(p)
        assert len(lista._cola) == 1

    def test_inscripcion_con_fecha_especifica(self):
        lista = _lista()
        p = _paciente(11111111)
        fecha = datetime(2026, 6, 10, 8, 0)
        lista.agregar_paciente_en_lista(p, fecha_inscripcion=fecha)
        assert lista._cola[0][1] == fecha

    def test_multiples_pacientes_se_inscriben(self):
        lista = _lista()
        for run in [11111111, 22222222, 33333333]:
            lista.agregar_paciente_en_lista(_paciente(run))
        assert len(lista._cola) == 3


# ---------------------------------------------------------------------------
# Extracción y prioridad
# ---------------------------------------------------------------------------


class TestExtraccion:
    def test_extraer_de_lista_vacia_devuelve_none(self):
        lista = _lista()
        assert lista.extraer_paciente_de_lista() is None

    def test_extrae_unico_paciente(self):
        lista = _lista()
        p = _paciente(11111111)
        lista.agregar_paciente_en_lista(p)
        extraido = lista.extraer_paciente_de_lista()
        assert extraido.RUN_usuario == p.RUN_usuario

    def test_lista_queda_vacia_despues_de_extraer(self):
        lista = _lista()
        lista.agregar_paciente_en_lista(_paciente(11111111))
        lista.extraer_paciente_de_lista()
        assert lista.extraer_paciente_de_lista() is None

    def test_urgente_sale_antes_que_normal(self):
        lista = _lista()
        p_normal  = _paciente(11111111)
        p_urgente = _paciente(22222222)
        fecha = datetime(2026, 6, 10, 8, 0)
        lista.agregar_paciente_en_lista(p_normal,  PrioridadEspera.NORMAL,  fecha)
        lista.agregar_paciente_en_lista(p_urgente, PrioridadEspera.URGENTE, fecha + timedelta(hours=1))
        extraido = lista.extraer_paciente_de_lista()
        assert extraido.RUN_usuario == p_urgente.RUN_usuario

    def test_misma_prioridad_sale_antes_el_mas_antiguo(self):
        lista = _lista()
        p1 = _paciente(11111111)
        p2 = _paciente(22222222)
        t1 = datetime(2026, 6, 10, 8, 0)
        t2 = datetime(2026, 6, 10, 9, 0)   # Llegó después
        lista.agregar_paciente_en_lista(p1, PrioridadEspera.NORMAL, t1)
        lista.agregar_paciente_en_lista(p2, PrioridadEspera.NORMAL, t2)
        extraido = lista.extraer_paciente_de_lista()
        assert extraido.RUN_usuario == p1.RUN_usuario

    def test_orden_completo_prioridades(self):
        lista = _lista()
        fecha_base = datetime(2026, 6, 10, 8, 0)
        runs = {
            PrioridadEspera.BAJA:    11111111,
            PrioridadEspera.NORMAL:  22222222,
            PrioridadEspera.ALTA:    33333333,
            PrioridadEspera.URGENTE: 44444444,
        }
        for prio, run in runs.items():
            lista.agregar_paciente_en_lista(_paciente(run), prio, fecha_base)

        orden_esperado = [44444444, 33333333, 22222222, 11111111]
        for run_esperado in orden_esperado:
            extraido = lista.extraer_paciente_de_lista()
            assert extraido.RUN_usuario == run_esperado


# ---------------------------------------------------------------------------
# Asignar hora disponible
# ---------------------------------------------------------------------------


class TestAsignarHora:
    def test_asignar_crea_cita_en_agenda_del_medico(self):
        lista = _lista()
        medico = _medico()
        paciente = _paciente(11111111)

        slot = SLOT_FUTURO.replace(hour=9, minute=0, second=0, microsecond=0)
        lista.asignar_hora_disponible(paciente, medico, slot)

        citas = medico.agenda.citas_del_dia(slot.date())
        assert len(citas) == 1
        assert citas[0].paciente_id == paciente.RUN_usuario

    def test_asignar_usa_especialidad_de_la_lista(self):
        lista = _lista()
        medico = _medico()
        paciente = _paciente(11111111)

        slot = SLOT_FUTURO.replace(hour=10, minute=0, second=0, microsecond=0)
        lista.asignar_hora_disponible(paciente, medico, slot)

        citas = medico.agenda.citas_del_dia(slot.date())
        assert citas[0].especialidad == ESPECIALIDAD_CARDIO.nombre


# ---------------------------------------------------------------------------
# Liberar y reasignar cupo
# ---------------------------------------------------------------------------


class TestLiberarReasignar:
    def test_cupo_asignado_si_paciente_acepta(self):
        lista = _lista()
        medico = _medico()
        paciente = _paciente(11111111)
        lista.agregar_paciente_en_lista(paciente)

        slot = SLOT_FUTURO.replace(hour=11, minute=0, second=0, microsecond=0)
        asignado = lista.liberar_reasignar_cupo_en_lista(medico, slot, respuesta_simulada="ACEPTA")

        assert asignado is True
        assert len(medico.agenda.citas_del_dia(slot.date())) == 1

    def test_cupo_no_asignado_si_lista_vacia(self):
        lista = _lista()
        medico = _medico()
        slot = SLOT_FUTURO.replace(hour=11, minute=0, second=0, microsecond=0)
        asignado = lista.liberar_reasignar_cupo_en_lista(medico, slot)
        assert asignado is False

    def test_paciente_que_rechaza_pero_mantiene_permanece_en_lista(self):
        lista = _lista()
        medico = _medico()
        paciente = _paciente(11111111)
        lista.agregar_paciente_en_lista(paciente)

        slot = SLOT_FUTURO.replace(hour=12, minute=0, second=0, microsecond=0)
        lista.liberar_reasignar_cupo_en_lista(
            medico, slot, respuesta_simulada="RECHAZA_PERO_MANTIENE"
        )

        # El paciente debe seguir en la lista
        assert len(lista._cola) == 1

    def test_paciente_que_rechaza_definitivamente_se_elimina(self):
        lista = _lista()
        medico = _medico()
        paciente = _paciente(11111111)
        lista.agregar_paciente_en_lista(paciente)

        slot = SLOT_FUTURO.replace(hour=13, minute=0, second=0, microsecond=0)
        lista.liberar_reasignar_cupo_en_lista(
            medico, slot, respuesta_simulada="RECHAZA_DEFINITIVAMENTE"
        )

        assert len(lista._cola) == 0
