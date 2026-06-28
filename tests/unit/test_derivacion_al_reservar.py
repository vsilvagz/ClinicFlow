"""Tests del enlace: reservar en la especialidad derivada cierra la derivación."""

from datetime import datetime, timedelta

from app.backend.domain.enums import EstadoDerivacion
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import MedicoORM, PacienteORM
from app.backend.repositories.derivaciones import RepositorioDerivaciones
from app.backend.schemas.citas import CitaCrear
from app.backend.schemas.derivaciones import DerivacionCrear
from app.backend.services.citas_service import crear_cita
from app.backend.services.derivaciones_service import emitir_derivacion

PACIENTE_RUN = 111111111
MEDICO_RUN = 222222222


def _seed(db, especialidad_medico="Cardiología"):
    esp = EspecialidadORM(nombre=especialidad_medico)
    db.add(esp)
    db.flush()
    db.add(PacienteORM(run_usuario=PACIENTE_RUN, nombre="Ana", correo="a@e.cl", telefono=1))
    db.add(
        MedicoORM(
            run_usuario=MEDICO_RUN,
            nombre="Dr. Pérez",
            correo="d@e.cl",
            telefono=2,
            especialidad_id=esp.id,
        )
    )
    db.commit()


def _emitir(db, especialidad_destino, dias=30):
    return emitir_derivacion(
        db,
        DerivacionCrear(
            paciente_id=PACIENTE_RUN,
            medico_origen_id=MEDICO_RUN,
            especialidad_destino=especialidad_destino,
            motivo="evaluación",
            dias_vigencia=dias,
        ),
    )


def test_reservar_en_especialidad_derivada_completa_la_derivacion(db):
    _seed(db, "Cardiología")
    deriv = _emitir(db, "Cardiología")

    futuro = datetime.now() + timedelta(days=3)
    cita = crear_cita(
        db, CitaCrear(paciente_id=PACIENTE_RUN, medico_id=MEDICO_RUN, inicio=futuro)
    )

    actualizada = RepositorioDerivaciones(db).obtener(deriv.id)
    assert actualizada.estado is EstadoDerivacion.COMPLETADA
    assert actualizada.cita_resultante_id == cita.id


def test_emparejamiento_ignora_mayusculas_y_tildes(db):
    # El médico atiende "Cardiología"; la derivación se escribió distinto.
    _seed(db, "Cardiología")
    deriv = _emitir(db, "cardiologia")

    futuro = datetime.now() + timedelta(days=3)
    crear_cita(
        db, CitaCrear(paciente_id=PACIENTE_RUN, medico_id=MEDICO_RUN, inicio=futuro)
    )

    assert RepositorioDerivaciones(db).obtener(deriv.id).estado is EstadoDerivacion.COMPLETADA


def test_reserva_en_otra_especialidad_no_toca_la_derivacion(db):
    _seed(db, "Cardiología")
    db.add(EspecialidadORM(nombre="Neurología"))
    db.commit()
    deriv = _emitir(db, "Neurología")  # derivado a Neurología, reserva en Cardiología

    futuro = datetime.now() + timedelta(days=3)
    crear_cita(
        db, CitaCrear(paciente_id=PACIENTE_RUN, medico_id=MEDICO_RUN, inicio=futuro)
    )

    deriv_actual = RepositorioDerivaciones(db).obtener(deriv.id)
    assert deriv_actual.estado is EstadoDerivacion.PENDIENTE
    assert deriv_actual.cita_resultante_id is None
