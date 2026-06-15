"""Tests de los tipos de usuario y sus permisos (enunciado 3.2)."""

from datetime import datetime, time, timedelta

import pytest

from app.backend.domain.agenda import Agenda, BloqueHorario
from app.backend.domain.citas import Cita
from app.backend.domain.clinica import Clinica
from app.backend.domain.enums import EstadoCita, EstadoDerivacion, PrioridadEspera
from app.backend.domain.especialidades import Especialidad
from app.backend.domain.lista_espera import Lista_de_Espera
from app.backend.domain.usuarios import Administrador, Medico, Paciente, Recepcionista

# ---------------------------------------------------------------------------
# Constantes de prueba
# ---------------------------------------------------------------------------

AHORA = datetime(2026, 6, 13, 10, 0)
MANANA = AHORA + timedelta(days=1)
DIA_MANANA = MANANA.weekday()

CARDIO = Especialidad("Cardiología")
NEURO  = Especialidad("Neurología")


def _clinica() -> Clinica:
    return Clinica("12345678-9", "Clínica Test")


def _medico(run: int = 22222222, especialidad: Especialidad = CARDIO) -> Medico:
    m = Medico(run, "Dr. Test", "doc@test.cl", 912345678, especialidad)
    m.agenda.agregar_horario(BloqueHorario(DIA_MANANA, time(8, 0), time(18, 0)))
    return m


def _paciente(run: int = 11111111) -> Paciente:
    return Paciente(run, "Paciente Test", "p@test.cl", 911111111)


def _cita(medico: Medico, inicio: datetime = None, ahora: datetime = AHORA) -> Cita:
    c = Cita.crear(
        paciente_id=11111111,
        medico_id=medico.RUN_usuario,
        especialidad=medico.especialidad.nombre,
        inicio=inicio or MANANA.replace(hour=9),
        ahora=ahora,
    )
    medico.agenda.agregar_cita(c)
    return c


# ---------------------------------------------------------------------------
# Usuario (base)
# ---------------------------------------------------------------------------


class TestUsuario:
    def test_run_usuario_es_inmutable(self):
        p = _paciente()
        with pytest.raises(AttributeError):
            p.RUN_usuario = 99999999  # type: ignore

    def test_nombre_setter(self):
        p = _paciente()
        p.nombre = "Nuevo Nombre"
        assert p.nombre == "Nuevo Nombre"

    def test_correo_setter_valido(self):
        p = _paciente()
        p.correo = "nuevo@correo.cl"
        assert p.correo == "nuevo@correo.cl"

    def test_correo_invalido_lanza_error(self):
        p = _paciente()
        with pytest.raises(ValueError):
            p.correo = "correo-sin-arroba"

    def test_telefono_setter(self):
        p = _paciente()
        p.telefono = 999999999
        assert p.telefono == 999999999


# ---------------------------------------------------------------------------
# Paciente
# ---------------------------------------------------------------------------


class TestPaciente:
    # ── Solicitar cita ────────────────────────────────────────────────────────

    def test_solicitar_cita_crea_y_registra(self):
        """Enunciado 3.2: el paciente puede solicitar citas."""
        p = _paciente()
        m = _medico()
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        assert cita in p.historial_citas()
        assert cita in m.agenda.citas_activas()

    def test_solicitar_cita_usa_especialidad_del_medico(self):
        p = _paciente()
        m = _medico(especialidad=CARDIO)
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        assert cita.especialidad == CARDIO.nombre

    def test_solicitar_cita_asigna_run_correcto(self):
        p = _paciente(11111111)
        m = _medico(22222222)
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        assert cita.paciente_id == 11111111
        assert cita.medico_id == 22222222

    # ── Cancelar cita ─────────────────────────────────────────────────────────

    def test_cancelar_cita(self):
        """Enunciado 3.2: el paciente puede cancelar horas."""
        p = _paciente()
        m = _medico()
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        p.cancelar_cita(cita)
        assert not cita.esta_activa

    # ── Reagendar cita ────────────────────────────────────────────────────────

    def test_reagendar_cita(self):
        """Enunciado 3.2: el paciente puede reagendar."""
        p = _paciente()
        m = _medico()
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        nueva = p.reagendar_cita(cita, m, MANANA.replace(hour=10), ahora=AHORA)

        assert nueva in p.historial_citas()
        assert nueva in m.agenda.citas_activas()
        from app.backend.domain.enums import EstadoCita
        assert cita.estado == EstadoCita.REAGENDADA

    # ── Consultar disponibilidad ──────────────────────────────────────────────

    def test_consultar_disponibilidad(self):
        """Enunciado 3.2: el paciente puede consultar disponibilidad."""
        p = _paciente()
        m = _medico()
        slots = p.consultar_disponibilidad(m, MANANA.date())
        assert len(slots) > 0

    def test_consultar_disponibilidad_excluye_citas_tomadas(self):
        p = _paciente()
        m = _medico()
        inicio = MANANA.replace(hour=9)
        p.solicitar_cita(m, inicio, ahora=AHORA)
        slots = p.consultar_disponibilidad(m, MANANA.date())
        assert inicio not in slots

    # ── Lista de espera ───────────────────────────────────────────────────────

    def test_inscribirse_en_lista_espera(self):
        """Enunciado 3.2: el paciente puede ingresar a listas de espera."""
        from app.backend.domain.clinica import Clinica
        from app.backend.domain.lista_espera import Lista_de_Espera
        p = _paciente()
        lista = Lista_de_Espera(CARDIO, Clinica("12345678-9", "Clínica Test"))
        resultado = p.inscribirse_en_lista_espera(lista)
        assert resultado is True

    def test_inscribirse_dos_veces_devuelve_false(self):
        from app.backend.domain.clinica import Clinica
        from app.backend.domain.lista_espera import Lista_de_Espera
        p = _paciente()
        lista = Lista_de_Espera(CARDIO, Clinica("12345678-9", "Clínica Test"))
        p.inscribirse_en_lista_espera(lista)
        assert p.inscribirse_en_lista_espera(lista) is False

    # ── Historial y múltiples citas ───────────────────────────────────────────

    def test_registrar_cita_agrega_al_historial(self):
        p = _paciente()
        m = _medico()
        cita = _cita(m)
        p.registrar_cita(cita)
        assert cita in p.historial_citas()

    def test_citas_activas_filtra_por_estado(self):
        p = _paciente()
        m = _medico()
        cita = _cita(m)
        p.registrar_cita(cita)
        cita.cancelar()
        assert cita not in p.citas_activas()

    def test_paciente_puede_tener_multiples_citas_activas(self):
        """Enunciado 3.2: Un paciente puede tener múltiples citas activas simultáneamente."""
        p = _paciente()
        m1 = _medico(22222222, CARDIO)
        m2 = _medico(33333333, NEURO)
        m2.agenda.agregar_horario(BloqueHorario(DIA_MANANA, time(8, 0), time(18, 0)))

        cita1 = p.solicitar_cita(m1, MANANA.replace(hour=9),  ahora=AHORA)
        cita2 = p.solicitar_cita(m2, MANANA.replace(hour=10), ahora=AHORA)

        assert len(p.citas_activas()) == 2

    def test_tiene_cita_en_especialidad_true(self):
        p = _paciente()
        m = _medico()
        p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        assert p.tiene_cita_en_especialidad(CARDIO.nombre) is True

    def test_tiene_cita_en_especialidad_false_si_cancelada(self):
        p = _paciente()
        m = _medico()
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        p.cancelar_cita(cita)
        assert p.tiene_cita_en_especialidad(CARDIO.nombre) is False

    def test_historial_incluye_citas_canceladas(self):
        p = _paciente()
        m = _medico()
        cita = p.solicitar_cita(m, MANANA.replace(hour=9), ahora=AHORA)
        p.cancelar_cita(cita)
        assert cita in p.historial_citas()


# ---------------------------------------------------------------------------
# Médico
# ---------------------------------------------------------------------------


class TestMedico:
    def test_medico_tiene_agenda(self):
        m = _medico()
        assert isinstance(m.agenda, Agenda)

    def test_especialidad_setter(self):
        m = _medico()
        m.especialidad = NEURO
        assert m.especialidad == NEURO

    def test_bloquear_horario_agrega_bloqueo(self):
        m = _medico()
        b = m.bloquear_horario(MANANA.replace(hour=10), MANANA.replace(hour=11), "Reunión")
        assert b.motivo == "Reunión"

    def test_suspender_agenda_cancela_citas_activas(self):
        m = _medico()
        cita = _cita(m, MANANA.replace(hour=9))

        _, canceladas = m.suspender_agenda(
            MANANA.replace(hour=8), MANANA.replace(hour=18), "Paro"
        )

        assert cita in canceladas
        assert not cita.esta_activa

    def test_emitir_derivacion_crea_y_registra(self):
        """Enunciado 3.1.4: el médico activa la derivación."""
        m = _medico()
        d = m.emitir_derivacion(
            paciente_id=11111111,
            especialidad_destino="Neurología",
            motivo="Evaluación neurológica",
            ahora=AHORA,
        )
        assert d.medico_origen_id == m.RUN_usuario
        assert d in m.historial_derivaciones()

    def test_derivaciones_vigentes_excluye_completadas(self):
        m = _medico()
        d = m.emitir_derivacion(11111111, "Neurología", "Control", ahora=AHORA)
        from uuid import uuid4
        d.completar(uuid4())
        assert d not in m.derivaciones_vigentes()

    def test_historial_derivaciones_incluye_todas(self):
        m = _medico()
        d1 = m.emitir_derivacion(11111111, "Neurología", "Control 1", ahora=AHORA)
        d2 = m.emitir_derivacion(22222222, "Pediatría",  "Control 2", ahora=AHORA)
        historial = m.historial_derivaciones()
        assert d1 in historial
        assert d2 in historial

    def test_eq_mismo_run(self):
        m1 = _medico(22222222)
        m2 = _medico(22222222)
        assert m1 == m2

    def test_eq_distinto_run(self):
        m1 = _medico(22222222)
        m2 = _medico(33333333)
        assert m1 != m2

    def test_hash_consistente_con_eq(self):
        m1 = _medico(22222222)
        m2 = _medico(22222222)
        assert hash(m1) == hash(m2)
        assert {m1, m2} == {m1}  # set deduplica por hash+eq


# ---------------------------------------------------------------------------
# Recepcionista
# ---------------------------------------------------------------------------


class TestRecepcionista:
    def _recep(self) -> Recepcionista:
        return Recepcionista(55555555, "Recep Test", "rec@test.cl", 933333333, _clinica())

    def test_confirmar_cita(self):
        """Enunciado 3.2: Recepcionistas pueden gestionar citas."""
        rec = self._recep()
        m = _medico()
        cita = _cita(m)
        rec.confirmar_cita(cita)
        assert cita.estado == EstadoCita.CONFIRMADA

    def test_cancelar_cita(self):
        rec = self._recep()
        m = _medico()
        cita = _cita(m)
        rec.cancelar_cita(cita)
        assert cita.estado == EstadoCita.CANCELADA

    def test_marcar_no_asistio(self):
        rec = self._recep()
        m = _medico()
        cita = _cita(m)
        cita.confirmar()
        rec.marcar_no_asistio(cita)
        assert cita.estado == EstadoCita.NO_ASISTIO

    def test_reagendar_cita(self):
        """Enunciado 3.2: Recepcionistas pueden reagendar pacientes."""
        rec = self._recep()
        m = _medico()
        cita = _cita(m, MANANA.replace(hour=9))
        nueva_inicio = MANANA.replace(hour=10)

        nueva = rec.reagendar_cita(cita, m, nueva_inicio, ahora=AHORA)

        assert cita.estado == EstadoCita.REAGENDADA
        assert nueva.inicio == nueva_inicio
        assert nueva.estado == EstadoCita.PENDIENTE

    def test_ver_agenda_medico(self):
        """Enunciado 3.2: Recepcionistas pueden visualizar agendas clínicas."""
        rec = self._recep()
        m = _medico()
        cita = _cita(m)
        agenda = rec.ver_agenda_medico(m, MANANA.date())
        assert cita in agenda

    def test_slots_disponibles_medico(self):
        rec = self._recep()
        m = _medico()
        slots = rec.slots_disponibles_medico(m, MANANA.date())
        assert len(slots) > 0

    def test_agregar_a_lista_espera(self):
        """Enunciado 3.2: Recepcionistas pueden administrar listas de espera."""
        rec = self._recep()
        lista = Lista_de_Espera(CARDIO, _clinica())
        p = _paciente()
        result = rec.agregar_a_lista_espera(lista, p)
        assert result is True

    def test_extraer_de_lista_espera(self):
        rec = self._recep()
        lista = Lista_de_Espera(CARDIO, _clinica())
        p = _paciente()
        lista.agregar_paciente_en_lista(p)
        extraido = rec.extraer_de_lista_espera(lista)
        assert extraido.RUN_usuario == p.RUN_usuario


# ---------------------------------------------------------------------------
# Administrador
# ---------------------------------------------------------------------------


class TestAdministrador:
    def test_crear_administrador(self):
        """Enunciado 3.2: El sistema tiene rol Administrador."""
        admin = Administrador(99999999, "Admin", "admin@test.cl", 900000000)
        assert admin.RUN_usuario == 99999999
        assert admin.nombre == "Admin"
