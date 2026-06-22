"""Carga de datos de ejemplo (seed) al arrancar la aplicación.

El objetivo es que, al levantar el contenedor por primera vez, la base de datos
ya tenga datos usables: especialidades, médicos con agenda y horarios, y algunos
pacientes. Así se puede demostrar el flujo completo (un paciente toma una hora)
sin tener que poblar nada a mano.

Decisiones de diseño:

- **Idempotente**: si ya existen especialidades, se asume que la BD está poblada
  y no se hace nada. Levantar la app muchas veces no duplica datos.
- **Reutiliza los servicios** (`crear_especialidad`, `crear_medico`,
  `crear_agenda`, …) en lugar de insertar filas a mano. Así las reglas de negocio
  y validaciones viven en un solo lugar y el seed prueba, de paso, esos casos de uso.
- **Sólo para desarrollo/demo**: se controla con el flag `settings.seed_demo`.
"""

from datetime import time

from sqlalchemy.orm import Session

from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.schemas.agendas import AgendaCrear, BloqueHorarioCrear
from app.backend.schemas.especialidades import EspecialidadCrear
from app.backend.schemas.usuarios import MedicoCrear, PacienteCrear
from app.backend.services.agendas_service import agregar_horario, crear_agenda
from app.backend.services.especialidades_service import crear_especialidad
from app.backend.services.usuarios_service import crear_medico, crear_paciente

# Atención de lunes (0) a viernes (4) en horario continuo de 08:00 a 20:00. Una
# sola franja por día (sin corte de almuerzo), de modo que siempre haya cupos en
# días hábiles.
_DIAS_HABILES = range(0, 5)  # 0=lunes … 4=viernes
_FRANJAS = [
    (time(8, 0), time(20, 0)),
]


def _sembrar_medico_con_agenda(
    db: Session, datos: MedicoCrear, franjas=_FRANJAS
) -> None:
    """Crea un médico, su agenda y los horarios recurrentes de atención."""
    medico = crear_medico(db, datos)
    agenda = crear_agenda(db, AgendaCrear(medico_run=medico.run_usuario))
    for dia in _DIAS_HABILES:
        for inicio, fin in franjas:
            agregar_horario(
                db,
                agenda.id,
                BloqueHorarioCrear(dia_semana=dia, hora_inicio=inicio, hora_fin=fin),
            )


def sembrar_datos_demo(db: Session) -> bool:
    """Puebla la BD con datos de ejemplo si está vacía.

    Devuelve True si se sembró, False si ya había datos y se omitió.
    """
    # Idempotencia: si ya hay especialidades, no volvemos a sembrar.
    if RepositorioEspecialidades(db).listar():
        return False

    # 1) Especialidades.
    cardiologia = crear_especialidad(
        db, EspecialidadCrear(nombre="Cardiología", descripcion="Salud del corazón.")
    )
    pediatria = crear_especialidad(
        db, EspecialidadCrear(nombre="Pediatría", descripcion="Atención infantil.")
    )
    general = crear_especialidad(
        db,
        EspecialidadCrear(
            nombre="Medicina General", descripcion="Atención de primer nivel."
        ),
    )

    # 2) Médicos con agenda y horarios.
    _sembrar_medico_con_agenda(
        db,
        MedicoCrear(
            run_usuario=11111111,
            nombre="Dra. Ana Rojas",
            correo="ana.rojas@clinicflow.cl",
            telefono=912345678,
            especialidad_id=cardiologia.id,
        ),
    )
    _sembrar_medico_con_agenda(
        db,
        MedicoCrear(
            run_usuario=22222222,
            nombre="Dr. Luis Pérez",
            correo="luis.perez@clinicflow.cl",
            telefono=912345679,
            especialidad_id=pediatria.id,
        ),
    )
    _sembrar_medico_con_agenda(
        db,
        MedicoCrear(
            run_usuario=33333333,
            nombre="Dra. Carla Núñez",
            correo="carla.nunez@clinicflow.cl",
            telefono=912345680,
            especialidad_id=general.id,
        ),
    )

    # 3) Pacientes de ejemplo.
    crear_paciente(
        db,
        PacienteCrear(
            run_usuario=44444444,
            nombre="Pedro Soto",
            correo="pedro.soto@example.cl",
            telefono=987654321,
        ),
    )
    crear_paciente(
        db,
        PacienteCrear(
            run_usuario=55555555,
            nombre="María González",
            correo="maria.gonzalez@example.cl",
            telefono=987654322,
        ),
    )

    return True
