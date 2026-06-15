"""Tests del ciclo de vida de las derivaciones médicas (enunciado 3.1.4)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.backend.domain.derivacion import Derivacion, DIAS_VIGENCIA_DEFAULT
from app.backend.domain.enums import EstadoDerivacion
from app.backend.domain.errores import TransicionEstadoInvalida

# ---------------------------------------------------------------------------
# Constantes de prueba
# ---------------------------------------------------------------------------

AHORA = datetime(2026, 6, 13, 10, 0)
PACIENTE_RUN  = 11111111
MEDICO_RUN    = 22222222
ESPECIALIDAD  = "Cardiología"
MOTIVO        = "Evaluación cardiológica post-operatoria"


def _derivacion(dias_vigencia: int = DIAS_VIGENCIA_DEFAULT, ahora: datetime = AHORA) -> Derivacion:
    return Derivacion.crear(
        paciente_id=PACIENTE_RUN,
        medico_origen_id=MEDICO_RUN,
        especialidad_destino=ESPECIALIDAD,
        motivo=MOTIVO,
        dias_vigencia=dias_vigencia,
        ahora=ahora,
    )


# ---------------------------------------------------------------------------
# Creación
# ---------------------------------------------------------------------------


class TestCrearDerivacion:
    def test_crea_en_estado_pendiente(self):
        d = _derivacion()
        assert d.estado == EstadoDerivacion.PENDIENTE

    def test_paciente_y_medico_correctos(self):
        d = _derivacion()
        assert d.paciente_id == PACIENTE_RUN
        assert d.medico_origen_id == MEDICO_RUN

    def test_especialidad_y_motivo_correctos(self):
        d = _derivacion()
        assert d.especialidad_destino == ESPECIALIDAD
        assert d.motivo == MOTIVO

    def test_expira_en_fecha_correcta(self):
        d = _derivacion(dias_vigencia=30, ahora=AHORA)
        esperado = AHORA + timedelta(days=30)
        assert d.expira_en == esperado

    def test_ids_son_unicos(self):
        a = _derivacion()
        b = _derivacion()
        assert a.id != b.id

    def test_vigencia_cero_lanza_error(self):
        with pytest.raises(ValueError):
            _derivacion(dias_vigencia=0)

    def test_vigencia_negativa_lanza_error(self):
        with pytest.raises(ValueError):
            _derivacion(dias_vigencia=-5)

    def test_especialidad_vacia_lanza_error(self):
        with pytest.raises(ValueError):
            Derivacion.crear(
                paciente_id=PACIENTE_RUN,
                medico_origen_id=MEDICO_RUN,
                especialidad_destino="   ",
                motivo=MOTIVO,
                ahora=AHORA,
            )

    def test_medico_destino_opcional(self):
        d = Derivacion.crear(
            paciente_id=PACIENTE_RUN,
            medico_origen_id=MEDICO_RUN,
            especialidad_destino=ESPECIALIDAD,
            motivo=MOTIVO,
            medico_destino_id=33333333,
            ahora=AHORA,
        )
        assert d.medico_destino_id == 33333333

    def test_medico_destino_none_por_defecto(self):
        d = _derivacion()
        assert d.medico_destino_id is None


# ---------------------------------------------------------------------------
# Completar (paciente agendó la cita derivada)
# ---------------------------------------------------------------------------


class TestCompletarDerivacion:
    def test_completar_cambia_estado_a_completada(self):
        d = _derivacion()
        cita_id = uuid4()
        d.completar(cita_id)
        assert d.estado == EstadoDerivacion.COMPLETADA

    def test_completar_guarda_cita_resultante(self):
        d = _derivacion()
        cita_id = uuid4()
        d.completar(cita_id)
        assert d.cita_resultante_id == cita_id

    def test_no_se_puede_completar_dos_veces(self):
        d = _derivacion()
        d.completar(uuid4())
        with pytest.raises(TransicionEstadoInvalida):
            d.completar(uuid4())

    def test_no_se_puede_completar_si_expirada(self):
        d = _derivacion()
        d.expirar()
        with pytest.raises(TransicionEstadoInvalida):
            d.completar(uuid4())


# ---------------------------------------------------------------------------
# Expirar (plazo venció)
# ---------------------------------------------------------------------------


class TestExpirarDerivacion:
    def test_expirar_cambia_estado_a_expirada(self):
        d = _derivacion()
        d.expirar()
        assert d.estado == EstadoDerivacion.EXPIRADA

    def test_no_se_puede_expirar_dos_veces(self):
        d = _derivacion()
        d.expirar()
        with pytest.raises(TransicionEstadoInvalida):
            d.expirar()

    def test_no_se_puede_expirar_si_completada(self):
        d = _derivacion()
        d.completar(uuid4())
        with pytest.raises(TransicionEstadoInvalida):
            d.expirar()


# ---------------------------------------------------------------------------
# Vigencia
# ---------------------------------------------------------------------------


class TestVigenciaDerivacion:
    def test_esta_vigente_cuando_pendiente_y_en_plazo(self):
        d = _derivacion(ahora=AHORA)
        # 15 días después de creación, dentro del plazo de 30 días
        assert d.esta_vigente(ahora=AHORA + timedelta(days=15))

    def test_no_esta_vigente_si_plazo_vencio(self):
        d = _derivacion(dias_vigencia=30, ahora=AHORA)
        assert not d.esta_vigente(ahora=AHORA + timedelta(days=31))

    def test_no_esta_vigente_si_completada(self):
        d = _derivacion()
        d.completar(uuid4())
        assert not d.esta_vigente(ahora=AHORA + timedelta(days=1))

    def test_no_esta_vigente_si_expirada(self):
        d = _derivacion()
        d.expirar()
        assert not d.esta_vigente(ahora=AHORA + timedelta(days=1))

    def test_verificar_expira_automaticamente_si_plazo_vencio(self):
        d = _derivacion(dias_vigencia=30, ahora=AHORA)
        expirada = d.verificar_y_expirar_si_corresponde(ahora=AHORA + timedelta(days=31))
        assert expirada is True
        assert d.estado == EstadoDerivacion.EXPIRADA

    def test_verificar_no_expira_si_dentro_del_plazo(self):
        d = _derivacion(dias_vigencia=30, ahora=AHORA)
        expirada = d.verificar_y_expirar_si_corresponde(ahora=AHORA + timedelta(days=15))
        assert expirada is False
        assert d.estado == EstadoDerivacion.PENDIENTE

    def test_verificar_no_expira_si_ya_completada(self):
        d = _derivacion(dias_vigencia=30, ahora=AHORA)
        d.completar(uuid4())
        # Aunque el plazo haya vencido, no reexpira una ya completada
        expirada = d.verificar_y_expirar_si_corresponde(ahora=AHORA + timedelta(days=31))
        assert expirada is False


# ---------------------------------------------------------------------------
# Propiedades
# ---------------------------------------------------------------------------


class TestPropiedadesDerivacion:
    def test_esta_activa_cuando_pendiente(self):
        d = _derivacion()
        assert d.esta_activa is True

    def test_no_esta_activa_cuando_completada(self):
        d = _derivacion()
        d.completar(uuid4())
        assert d.esta_activa is False

    def test_no_esta_activa_cuando_expirada(self):
        d = _derivacion()
        d.expirar()
        assert d.esta_activa is False
