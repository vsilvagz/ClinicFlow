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

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.backend.domain.enums import PrioridadEspera
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.mensajes import MensajeORM
from app.backend.models.usuarios import MedicoORM
from app.backend.repositories.agendas import RepositorioAgendas
from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.schemas.agendas import (
    AgendaCrear,
    BloqueHorarioCrear,
    BloqueoCrear,
    SuspensionCrear,
)
from app.backend.schemas.citas import CitaCrear
from app.backend.schemas.clinica import ClinicaCrear
from app.backend.schemas.derivaciones import DerivacionCrear
from app.backend.schemas.especialidades import EspecialidadCrear
from app.backend.schemas.lista_espera import InscripcionCrear, ListaEsperaCrear
from app.backend.schemas.usuarios import (
    AdministradorCrear,
    MedicoCrear,
    PacienteCrear,
    RecepcionistaCrear,
)
from app.backend.services.agendas_service import (
    agregar_horario,
    bloquear_horario,
    crear_agenda,
    suspender_agenda,
)
from app.backend.services.citas_service import cancelar_cita, confirmar_cita, crear_cita
from app.backend.services.clinica_service import crear_clinica
from app.backend.services.derivaciones_service import emitir_derivacion
from app.backend.services.especialidades_service import crear_especialidad
from app.backend.services.lista_espera_service import (
    inscribir_paciente,
    obtener_o_crear_lista,
)
from app.backend.services.usuarios_service import (
    crear_administrador,
    crear_medico,
    crear_paciente,
    crear_recepcionista,
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

# Clínica (sucursal) y su recepcionista. La recepcionista trabaja en esta clínica.
_CLINICA = ("76543210-9", "ClinicFlow Providencia", "Av. Providencia 1234, Santiago")
_RECEPCIONISTA = (12000001, "Lucía Ramírez")

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


def _proximos_dias_habiles(cantidad: int) -> list[date]:
    """Devuelve los próximos `cantidad` días hábiles a partir de mañana.

    Empezar desde mañana garantiza que las horas sembradas queden siempre en el
    futuro, sin importar la hora a la que se levante la aplicación.
    """
    dias: list[date] = []
    cursor = date.today() + timedelta(days=1)
    while len(dias) < cantidad:
        if cursor.weekday() < 5:  # 0=lunes … 4=viernes
            dias.append(cursor)
        cursor += timedelta(days=1)
    return dias


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

    # 5) Clínica (sucursal) y su recepcionista.
    rut_clinica, nombre_clinica, dir_clinica = _CLINICA
    clinica = crear_clinica(
        db, ClinicaCrear(rut_empresa=rut_clinica, nombre=nombre_clinica, direccion=dir_clinica)
    )
    run_recep, nombre_recep = _RECEPCIONISTA
    crear_recepcionista(
        db,
        RecepcionistaCrear(
            run_usuario=run_recep,
            nombre=nombre_recep,
            correo=_correo(nombre_recep, "clinicflow.cl"),
            telefono=940000000,
            clinica_rut=rut_clinica,
            password=_PASSWORD_DEMO,
        ),
    )

    # La clínica ofrece todas las especialidades y agrupa a todos los médicos
    # (relaciones muchos-a-muchos).
    for run, _, _ in _MEDICOS:
        clinica.medicos.append(db.get(MedicoORM, run))
    for esp_id in id_por_especialidad.values():
        clinica.especialidades.append(db.get(EspecialidadORM, esp_id))
    db.commit()

    # 6) Citas de ejemplo en los próximos días hábiles, con estados variados.
    d1, d2, d3, d4 = _proximos_dias_habiles(4)

    def _dt(dia: date, hora: int) -> datetime:
        return datetime.combine(dia, time(hora, 0))

    cita_pres = crear_cita(
        db, CitaCrear(paciente_id=44444444, medico_id=11000001, inicio=_dt(d1, 9), motivo="Control de presión")
    )
    confirmar_cita(db, cita_pres.id)  # confirmada
    crear_cita(
        db, CitaCrear(paciente_id=55555555, medico_id=11000003, inicio=_dt(d1, 10), motivo="Control niño sano")
    )  # pendiente
    cita_chequeo = crear_cita(
        db, CitaCrear(paciente_id=16000001, medico_id=11000005, inicio=_dt(d2, 11), motivo="Chequeo general")
    )
    confirmar_cita(db, cita_chequeo.id)  # confirmada
    cita_derma = crear_cita(
        db, CitaCrear(paciente_id=16000003, medico_id=11000007, inicio=_dt(d1, 12), motivo="Revisión de lunar")
    )
    cancelar_cita(db, cita_derma.id)  # cancelada

    # 7) Bloqueo y suspensión de agenda (en médicos sin citas en esos tramos).
    agenda_bloqueo = RepositorioAgendas(db).obtener_por_medico(11000002)
    bloquear_horario(
        db, agenda_bloqueo.id,
        BloqueoCrear(inicio=_dt(d3, 13), fin=_dt(d3, 15), motivo="Reunión clínica"),
    )
    agenda_susp = RepositorioAgendas(db).obtener_por_medico(11000004)
    suspender_agenda(
        db, agenda_susp.id,
        SuspensionCrear(inicio=_dt(d4, 8), fin=_dt(d4, 20), motivo="Capacitación"),
    )

    # 8) Lista de espera de Cardiología con pacientes priorizados.
    lista = obtener_o_crear_lista(
        db, ListaEsperaCrear(especialidad_id=id_por_especialidad["Cardiología"], clinica_rut=rut_clinica)
    )
    inscribir_paciente(db, lista.id, InscripcionCrear(paciente_id=16000004, prioridad=PrioridadEspera.NORMAL))
    inscribir_paciente(db, lista.id, InscripcionCrear(paciente_id=16000005, prioridad=PrioridadEspera.ALTA))
    inscribir_paciente(db, lista.id, InscripcionCrear(paciente_id=16000006, prioridad=PrioridadEspera.URGENTE))

    # 9) Una derivación con su mensaje al paciente, más un recordatorio.
    emitir_derivacion(
        db,
        DerivacionCrear(
            paciente_id=44444444,
            medico_origen_id=11000005,
            especialidad_destino="Cardiología",
            motivo="Evaluación de soplo cardíaco",
            dias_vigencia=30,
        ),
    )
    db.add(MensajeORM(
        paciente_id=44444444,
        tipo="DERIVACION",
        contenido=(
            "Tu médico Carla Núñez te ha derivado a Cardiología. "
            "Motivo: Evaluación de soplo cardíaco. Reserva una hora desde el portal."
        ),
    ))
    db.add(MensajeORM(
        paciente_id=55555555,
        tipo="RECORDATORIO",
        contenido="Recuerda tu próxima hora de Pediatría. Si no puedes asistir, cancélala con anticipación.",
    ))
    db.commit()

    return True
