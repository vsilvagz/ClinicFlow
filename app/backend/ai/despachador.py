"""Despachador: ejecuta una intención del asistente sobre los servicios reales.

Recibe una `IntencionAsistente` ya asociada a un paciente autenticado y la
traduce a llamadas concretas de la capa de servicios. Toda la validación y las
reglas de negocio siguen viviendo en `services/` y `domain/`: aquí solo se
resuelven nombres a identificadores y se arma un texto de respuesta para el
paciente.
"""

import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.domain.citas import ESTADOS_ACTIVOS
from app.backend.domain.errores import (
    AgendaSuspendida,
    CitaDuplicadaEnPeriodo,
    CitaEnPasadoError,
    ClinicFlowError,
    ConflictoDeAgenda,
    HorarioNoDisponible,
    ListaEsperaLlena,
    PacienteYaEnEspera,
    TransicionEstadoInvalida,
)
from app.backend.repositories.citas import RepositorioCitas
from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.repositories.lista_espera import RepositorioListaEspera
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.citas import CitaCrear, CitaReagendar
from app.backend.schemas.lista_espera import InscripcionCrear
from app.backend.services import agendas_service, citas_service, lista_espera_service

# Cuántas horas libres se ofrecen como máximo en una respuesta, para no abrumar.
MAX_SLOTS_OFRECIDOS = 5

# Traducción de cada error de negocio a un mensaje cordial para el paciente. Los
# errores del dominio traen detalles técnicos (RUN, ids); aquí los suavizamos.
_MENSAJES_ERROR: list[tuple[type, str]] = [
    (ConflictoDeAgenda, "Ese horario ya está ocupado. Prueba con otra hora."),
    (CitaEnPasadoError, "No puedo agendar una hora en el pasado."),
    (HorarioNoDisponible, "El médico no atiende en ese horario."),
    (AgendaSuspendida, "La agenda del médico está suspendida en esa fecha."),
    (CitaDuplicadaEnPeriodo,
     "Ya tienes una cita de esa especialidad muy cercana a esa fecha."),
    (TransicionEstadoInvalida,
     "No se puede realizar esa acción sobre la cita en su estado actual."),
    (PacienteYaEnEspera, "Ya estás inscrito en esa lista de espera."),
    (ListaEsperaLlena, "La lista de espera está llena por ahora."),
]


def _mensaje_de_error(exc: ClinicFlowError) -> str:
    """Devuelve el mensaje amable correspondiente a un error de negocio."""
    for tipo, mensaje in _MENSAJES_ERROR:
        if isinstance(exc, tipo):
            return mensaje
    return "No se pudo completar la solicitud."


# ──────────────────────────────────────────────────────────────────────────────
# Helpers puros (sin base de datos): normalización, emparejamiento y formato.
# ──────────────────────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios sobrantes, para comparar nombres."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return sin_tildes.strip().lower()


def emparejar_nombre(consulta: str, candidatos: list[str]) -> str | None:
    """Elige el candidato que mejor coincide con la consulta del paciente.

    Compara sin distinguir mayúsculas ni tildes: primero busca una coincidencia
    exacta y, si no la hay, una contención en cualquier dirección (por ejemplo
    'cardio' contra 'Cardiología'). Devuelve el nombre original o None.
    """
    if not consulta:
        return None
    objetivo = _normalizar(consulta)
    normalizados = [(c, _normalizar(c)) for c in candidatos]
    for original, norm in normalizados:
        if norm == objetivo:
            return original
    for original, norm in normalizados:
        if objetivo in norm or norm in objetivo:
            return original
    return None


def formatear_citas(citas) -> str:
    """Arma el listado de citas del paciente en texto legible."""
    if not citas:
        return "No tienes citas activas."
    lineas = ["Tus citas:"]
    for c in sorted(citas, key=lambda x: x.inicio):
        lineas.append(
            f"- {c.especialidad}: {c.inicio.strftime('%d-%m-%Y %H:%M')} ({c.estado.value})"
        )
    return "\n".join(lineas)


# ──────────────────────────────────────────────────────────────────────────────
# Acciones de solo lectura.
# ──────────────────────────────────────────────────────────────────────────────

def _consultar_mis_citas(db: Session, paciente_id: int) -> str:
    citas = RepositorioCitas(db).listar_de_paciente(paciente_id)
    activas = [c for c in citas if c.estado in ESTADOS_ACTIVOS]
    return formatear_citas(activas)


def _consultar_disponibilidad(
    db: Session, intencion: IntencionAsistente, ahora: datetime
) -> str:
    if not intencion.especialidad:
        return "¿De qué especialidad quieres consultar disponibilidad?"

    repo_esp = RepositorioEspecialidades(db)
    nombres = [e.nombre for e in repo_esp.listar()]
    nombre = emparejar_nombre(intencion.especialidad, nombres)
    if nombre is None:
        return f"No encontré la especialidad «{intencion.especialidad}»."

    especialidad = repo_esp.obtener_por_nombre(nombre)
    medicos = RepositorioUsuarios(db).listar_medicos_por_especialidad(especialidad.id)
    fecha = (intencion.fecha_hora or ahora).date()

    libres: list[tuple] = []
    for medico in medicos:
        for slot in agendas_service.slots_disponibles_de_medico(
            db, medico.run_usuario, fecha, ahora
        ):
            libres.append((medico, slot))

    fecha_txt = fecha.strftime("%d-%m-%Y")
    if not libres:
        return f"No hay horas de {nombre} disponibles para el {fecha_txt}."

    libres.sort(key=lambda ms: ms[1])
    lineas = [f"Horas de {nombre} para el {fecha_txt}:"]
    for medico, slot in libres[:MAX_SLOTS_OFRECIDOS]:
        lineas.append(f"- {slot.strftime('%H:%M')} con {medico.nombre}")
    return "\n".join(lineas)


# ──────────────────────────────────────────────────────────────────────────────
# Resolución compartida y acciones que modifican datos.
# ──────────────────────────────────────────────────────────────────────────────

def _resolver_especialidad(db: Session, texto: str | None):
    """Encuentra la EspecialidadORM que mejor coincide con el texto, o None."""
    repo = RepositorioEspecialidades(db)
    nombre = emparejar_nombre(texto or "", [e.nombre for e in repo.listar()])
    return repo.obtener_por_nombre(nombre) if nombre else None


def _buscar_citas_activas(db: Session, paciente_id: int, especialidad_texto: str | None):
    """Citas activas del paciente, filtradas por especialidad si se indicó."""
    citas = [
        c for c in RepositorioCitas(db).listar_de_paciente(paciente_id)
        if c.estado in ESTADOS_ACTIVOS
    ]
    if especialidad_texto and citas:
        objetivo = emparejar_nombre(especialidad_texto, [c.especialidad for c in citas])
        if objetivo:
            citas = [c for c in citas if c.especialidad == objetivo]
    return citas


def _pedir_especificar(citas, accion: str) -> str:
    detalle = ", ".join(
        f"{c.especialidad} ({c.inicio.strftime('%d-%m-%Y %H:%M')})" for c in citas
    )
    return f"Tienes varias citas activas. ¿Cuál quieres {accion}? {detalle}"


def _medico_para_slot(db: Session, medicos, fecha_hora: datetime, ahora: datetime):
    """Primer médico cuya agenda tiene libre exactamente ese horario, o None."""
    for medico in medicos:
        slots = agendas_service.slots_disponibles_de_medico(
            db, medico.run_usuario, fecha_hora.date(), ahora
        )
        if fecha_hora in slots:
            return medico
    return None


def _agendar(db: Session, paciente_id: int, intencion: IntencionAsistente, ahora: datetime) -> str:
    if not intencion.especialidad:
        return "¿De qué especialidad necesitas la hora?"
    if intencion.fecha_hora is None:
        return "¿Para qué fecha y hora quieres la cita?"

    especialidad = _resolver_especialidad(db, intencion.especialidad)
    if especialidad is None:
        return f"No encontré la especialidad «{intencion.especialidad}»."

    medicos = RepositorioUsuarios(db).listar_medicos_por_especialidad(especialidad.id)
    medico = _medico_para_slot(db, medicos, intencion.fecha_hora, ahora)
    if medico is None:
        # No existe ese horario exacto: ofrecemos las horas libres del día.
        return _consultar_disponibilidad(db, intencion, ahora)

    try:
        cita = citas_service.crear_cita(
            db,
            CitaCrear(
                paciente_id=paciente_id,
                medico_id=medico.run_usuario,
                inicio=intencion.fecha_hora,
                motivo=intencion.motivo or "",
            ),
            ahora=ahora,
        )
    except ClinicFlowError as exc:
        return _mensaje_de_error(exc)

    return (
        f"Listo, agendé tu hora de {especialidad.nombre} con {medico.nombre} "
        f"el {cita.inicio.strftime('%d-%m-%Y %H:%M')}."
    )


def _cancelar(db: Session, paciente_id: int, intencion: IntencionAsistente) -> str:
    citas = _buscar_citas_activas(db, paciente_id, intencion.especialidad)
    if not citas:
        return "No encontré una cita activa para cancelar."
    if len(citas) > 1:
        return _pedir_especificar(citas, "cancelar")

    cita = citas[0]
    try:
        citas_service.cancelar_cita(db, cita.id)
    except ClinicFlowError as exc:
        return _mensaje_de_error(exc)
    return (
        f"Cancelé tu cita de {cita.especialidad} "
        f"del {cita.inicio.strftime('%d-%m-%Y %H:%M')}."
    )


def _reagendar(
    db: Session, paciente_id: int, intencion: IntencionAsistente, ahora: datetime
) -> str:
    if intencion.nueva_fecha_hora is None:
        return "¿A qué nueva fecha y hora quieres mover tu cita?"

    citas = _buscar_citas_activas(db, paciente_id, intencion.especialidad)
    if not citas:
        return "No encontré una cita activa para reagendar."
    if len(citas) > 1:
        return _pedir_especificar(citas, "reagendar")

    cita = citas[0]
    try:
        nueva = citas_service.reagendar_cita(
            db, cita.id, CitaReagendar(nueva_inicio=intencion.nueva_fecha_hora), ahora=ahora
        )
    except ClinicFlowError as exc:
        return _mensaje_de_error(exc)
    return (
        f"Reagendé tu cita de {cita.especialidad} "
        f"para el {nueva.inicio.strftime('%d-%m-%Y %H:%M')}."
    )


def _inscribir_espera(db: Session, paciente_id: int, intencion: IntencionAsistente) -> str:
    if not intencion.especialidad:
        return "¿En la lista de espera de qué especialidad quieres inscribirte?"

    especialidad = _resolver_especialidad(db, intencion.especialidad)
    if especialidad is None:
        return f"No encontré la especialidad «{intencion.especialidad}»."

    listas = [
        lst for lst in RepositorioListaEspera(db).listar()
        if lst.especialidad_id == especialidad.id
    ]
    if not listas:
        return f"No hay una lista de espera de {especialidad.nombre} por ahora."

    datos = InscripcionCrear(
        paciente_id=paciente_id,
        prioridad=intencion.prioridad or InscripcionCrear.model_fields["prioridad"].default,
    )
    try:
        lista_espera_service.inscribir_paciente(db, listas[0].id, datos)
    except ClinicFlowError as exc:
        return _mensaje_de_error(exc)
    return f"Te inscribí en la lista de espera de {especialidad.nombre}."


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada.
# ──────────────────────────────────────────────────────────────────────────────

def despachar(
    db: Session,
    paciente_id: int,
    intencion: IntencionAsistente,
    ahora: datetime | None = None,
) -> str:
    """Ejecuta la intención para el paciente dado y devuelve el texto de respuesta."""
    ahora = ahora or datetime.now()

    if intencion.accion is AccionAsistente.CONSULTAR_MIS_CITAS:
        return _consultar_mis_citas(db, paciente_id)
    if intencion.accion is AccionAsistente.CONSULTAR_DISPONIBILIDAD:
        return _consultar_disponibilidad(db, intencion, ahora)
    if intencion.accion is AccionAsistente.AGENDAR:
        return _agendar(db, paciente_id, intencion, ahora)
    if intencion.accion is AccionAsistente.CANCELAR:
        return _cancelar(db, paciente_id, intencion)
    if intencion.accion is AccionAsistente.REAGENDAR:
        return _reagendar(db, paciente_id, intencion, ahora)
    if intencion.accion is AccionAsistente.INSCRIBIR_ESPERA:
        return _inscribir_espera(db, paciente_id, intencion)

    return intencion.respuesta or "No entendí tu solicitud. ¿Puedes reformularla?"
