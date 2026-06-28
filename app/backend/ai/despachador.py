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
from app.backend.repositories.citas import RepositorioCitas
from app.backend.repositories.especialidades import RepositorioEspecialidades
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.services import agendas_service

# Cuántas horas libres se ofrecen como máximo en una respuesta, para no abrumar.
MAX_SLOTS_OFRECIDOS = 5


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
    if intencion.accion is AccionAsistente.DESCONOCIDA:
        return intencion.respuesta or "No entendí tu solicitud. ¿Puedes reformularla?"

    # Acciones que modifican datos (agendar, cancelar, reagendar, lista de
    # espera) se implementan en el paso siguiente.
    return "Esa acción todavía no está disponible por el asistente."
