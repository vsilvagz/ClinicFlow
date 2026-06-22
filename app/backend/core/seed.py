"""Carga de datos de ejemplo (seed) al arrancar la aplicación.

El objetivo es que, al levantar el contenedor por primera vez, la base de datos
ya tenga datos usables: especialidades, médicos con agenda y horarios, y varios
pacientes. Así se puede demostrar el flujo completo (un paciente toma una hora)
sin tener que poblar nada a mano.

Decisiones de diseño:

- **Idempotente**: si ya existen especialidades, se asume que la BD está poblada
  y no se hace nada. Levantar la app muchas veces no duplica datos.
- **Dirigido por datos**: las entidades a crear se declaran en listas al inicio y
  un par de bucles las insertan, reutilizando los servicios (`crear_especialidad`,
  `crear_medico`, …). Así las reglas de negocio viven en un solo lugar y agregar
  datos nuevos es solo editar las listas.
- **Sólo para desarrollo/demo**: se controla con el flag `settings.seed_demo`.
"""

from datetime import time

from sqlalchemy.orm import Session

from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.schemas.agendas import AgendaCrear, BloqueHorarioCrear
from app.backend.schemas.especialidades import EspecialidadCrear
from app.backend.schemas.usuarios import AdministradorCrear, MedicoCrear, PacienteCrear
from app.backend.services.agendas_service import agregar_horario, crear_agenda
from app.backend.services.especialidades_service import crear_especialidad
from app.backend.services.usuarios_service import (
    crear_administrador,
    crear_medico,
    crear_paciente,
)

# Contraseña por defecto de todos los usuarios sembrados (solo para la demo).
_PASSWORD_DEMO = "demo1234"

# Atención de lunes (0) a viernes (4) en horario continuo de 08:00 a 20:00. Una
# sola franja por día (sin corte de almuerzo), de modo que siempre haya cupos en
# días hábiles.
_DIAS_HABILES = range(0, 5)  # 0=lunes … 4=viernes
_FRANJA = (time(8, 0), time(20, 0))

# ──────────────────────────────────────────────────────────────────────────────
# Datos a sembrar. Editar estas listas para agregar más.
# ──────────────────────────────────────────────────────────────────────────────

# (nombre, descripción)
_ESPECIALIDADES = [
    ("Medicina General", "Atención de primer nivel y derivaciones."),
    ("Cardiología", "Diagnóstico y tratamiento del corazón."),
    ("Pediatría", "Atención de niños y adolescentes."),
    ("Dermatología", "Enfermedades de la piel."),
    ("Traumatología", "Lesiones de huesos, músculos y articulaciones."),
    ("Ginecología", "Salud femenina y control prenatal."),
    ("Oftalmología", "Salud visual y enfermedades del ojo."),
    ("Neurología", "Trastornos del sistema nervioso."),
    ("Psiquiatría", "Salud mental y trastornos del ánimo."),
    ("Otorrinolaringología", "Oído, nariz y garganta."),
]

# (run, nombre, especialidad). El correo y el teléfono se generan automáticamente.
_MEDICOS = [
    (11000001, "Ana Rojas", "Cardiología"),
    (11000002, "Marcos Vidal", "Cardiología"),
    (11000003, "Luis Pérez", "Pediatría"),
    (11000004, "Camila Fuentes", "Pediatría"),
    (11000005, "Carla Núñez", "Medicina General"),
    (11000006, "Felipe Soto", "Medicina General"),
    (11000007, "Valentina Reyes", "Dermatología"),
    (11000008, "Tomás Herrera", "Traumatología"),
    (11000009, "Josefa Morales", "Traumatología"),
    (11000010, "Paula Castro", "Ginecología"),
    (11000011, "Andrés Lagos", "Oftalmología"),
    (11000012, "Daniela Silva", "Neurología"),
    (11000013, "Rodrigo Tapia", "Psiquiatría"),
    (11000014, "Francisca Díaz", "Otorrinolaringología"),
]

# (run, nombre)
_PACIENTES = [
    (44444444, "Pedro Soto"),
    (55555555, "María González"),
    (16000001, "Javiera Muñoz"),
    (16000002, "Diego Araya"),
    (16000003, "Catalina Rivas"),
    (16000004, "Sebastián Vera"),
    (16000005, "Antonia Pizarro"),
    (16000006, "Matías Cáceres"),
]


def _correo(nombre: str, dominio: str) -> str:
    """Genera un correo simple a partir del nombre (sin tildes ni títulos)."""
    base = (
        nombre.lower()
        .replace("dra. ", "")
        .replace("dr. ", "")
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        .replace(" ", ".")
    )
    return f"{base}@{dominio}"


def _sembrar_medico_con_agenda(db: Session, datos: MedicoCrear) -> None:
    """Crea un médico, su agenda y los horarios recurrentes de atención."""
    medico = crear_medico(db, datos)
    agenda = crear_agenda(db, AgendaCrear(medico_run=medico.run_usuario))
    inicio, fin = _FRANJA
    for dia in _DIAS_HABILES:
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

    # 1) Especialidades (guardamos el id por nombre para asignarlo a los médicos).
    id_por_especialidad: dict[str, int] = {}
    for nombre, descripcion in _ESPECIALIDADES:
        esp = crear_especialidad(db, EspecialidadCrear(nombre=nombre, descripcion=descripcion))
        id_por_especialidad[nombre] = esp.id

    # 2) Médicos con agenda y horarios.
    for i, (run, nombre, especialidad) in enumerate(_MEDICOS):
        _sembrar_medico_con_agenda(
            db,
            MedicoCrear(
                run_usuario=run,
                nombre=nombre,
                correo=_correo(nombre, "clinicflow.cl"),
                telefono=920000000 + i,
                especialidad_id=id_por_especialidad[especialidad],
                password=_PASSWORD_DEMO,
            ),
        )

    # 3) Pacientes de ejemplo.
    for i, (run, nombre) in enumerate(_PACIENTES):
        crear_paciente(
            db,
            PacienteCrear(
                run_usuario=run,
                nombre=nombre,
                correo=_correo(nombre, "example.cl"),
                telefono=930000000 + i,
                password=_PASSWORD_DEMO,
            ),
        )

    # 4) Un administrador para acceder al portal de gestión.
    crear_administrador(
        db,
        AdministradorCrear(
            run_usuario=10000000,
            nombre="Administrador",
            correo="admin@clinicflow.cl",
            telefono=910000000,
            password=_PASSWORD_DEMO,
        ),
    )

    return True
