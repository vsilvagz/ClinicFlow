"""Casos de uso sobre derivaciones médicas.

Reutiliza la entidad de dominio `Derivacion` para toda la lógica: la creación
valida la vigencia y la especialidad destino, y las transiciones de estado
(completar/expirar) pasan por su máquina de estados. El servicio solo traduce
entre ORM y dominio y persiste el resultado.
"""

import unicodedata
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.backend.domain.derivacion import Derivacion
from app.backend.domain.errores import (
    DerivacionNoEncontrada,
    MedicoNoEncontrado,
    PacienteNoEncontrado,
)
from app.backend.models.derivacion import DerivacionORM
from app.backend.repositories.derivaciones import RepositorioDerivaciones
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.derivaciones import DerivacionCrear

# ──────────────────────────────────────────────────────────────────────────────
# Traducción ORM ↔ dominio.
# ──────────────────────────────────────────────────────────────────────────────

def _a_dominio(orm: DerivacionORM) -> Derivacion:
    """Reconstruye la entidad de dominio a partir de la fila ORM."""
    return Derivacion(
        id=orm.id,
        paciente_id=orm.paciente_id,
        medico_origen_id=orm.medico_origen_id,
        especialidad_destino=orm.especialidad_destino,
        motivo=orm.motivo,
        estado=orm.estado,
        creada_en=orm.creada_en,
        expira_en=orm.expira_en,
        medico_destino_id=orm.medico_destino_id,
        cita_resultante_id=orm.cita_resultante_id,
        notas=orm.notas,
    )


def _a_orm(deriv: Derivacion) -> DerivacionORM:
    """Crea una fila ORM nueva a partir de una entidad de dominio."""
    return DerivacionORM(
        id=deriv.id,
        paciente_id=deriv.paciente_id,
        medico_origen_id=deriv.medico_origen_id,
        especialidad_destino=deriv.especialidad_destino,
        motivo=deriv.motivo,
        estado=deriv.estado,
        creada_en=deriv.creada_en,
        expira_en=deriv.expira_en,
        medico_destino_id=deriv.medico_destino_id,
        cita_resultante_id=deriv.cita_resultante_id,
        notas=deriv.notas,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Casos de uso.
# ──────────────────────────────────────────────────────────────────────────────

def emitir_derivacion(
    db: Session, datos: DerivacionCrear, ahora: datetime | None = None
) -> DerivacionORM:
    """Un médico emite una derivación hacia otra especialidad."""
    usuarios = RepositorioUsuarios(db)
    if usuarios.obtener_paciente(datos.paciente_id) is None:
        raise PacienteNoEncontrado(f"No existe un paciente con RUN {datos.paciente_id}.")
    if usuarios.obtener_medico(datos.medico_origen_id) is None:
        raise MedicoNoEncontrado(
            f"No existe un médico con RUN {datos.medico_origen_id}."
        )

    # El dominio valida la vigencia y la especialidad destino y fija la expiración.
    deriv_dom = Derivacion.crear(
        paciente_id=datos.paciente_id,
        medico_origen_id=datos.medico_origen_id,
        especialidad_destino=datos.especialidad_destino,
        motivo=datos.motivo,
        dias_vigencia=datos.dias_vigencia,
        medico_destino_id=datos.medico_destino_id,
        notas=datos.notas,
        ahora=ahora,
    )

    orm = RepositorioDerivaciones(db).agregar(_a_orm(deriv_dom))
    db.commit()
    db.refresh(orm)
    return orm


def completar_derivacion(db: Session, derivacion_id: UUID, cita_id: UUID) -> DerivacionORM:
    """Marca la derivación como COMPLETADA y la vincula a la cita resultante."""
    repo = RepositorioDerivaciones(db)
    orm = repo.obtener(derivacion_id)
    if orm is None:
        raise DerivacionNoEncontrada(f"No existe la derivación {derivacion_id}.")

    deriv_dom = _a_dominio(orm)
    deriv_dom.completar(cita_id)        # puede lanzar TransicionEstadoInvalida.
    orm.estado = deriv_dom.estado
    orm.cita_resultante_id = deriv_dom.cita_resultante_id
    db.commit()
    db.refresh(orm)
    return orm


def _normalizar_especialidad(nombre: str) -> str:
    """Nombre de especialidad sin tildes ni mayúsculas, para comparar de forma laxa."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", nombre)
        if not unicodedata.combining(c)
    )
    return sin_tildes.strip().casefold()


def completar_por_reserva(
    db: Session,
    paciente_id: int,
    especialidad: str,
    cita_id: UUID,
    ahora: datetime | None = None,
) -> DerivacionORM | None:
    """Cierra la derivación pendiente del paciente para la especialidad reservada.

    Cuando el paciente toma una hora en una especialidad a la que estaba derivado
    —y la derivación sigue vigente— la marca COMPLETADA y la enlaza a la cita
    recién creada. Devuelve la derivación cerrada, o None si no había ninguna
    aplicable. Es idempotente respecto de derivaciones ya cerradas: solo mira las
    pendientes.
    """
    repo = RepositorioDerivaciones(db)
    objetivo = _normalizar_especialidad(especialidad)
    for orm in repo.listar_pendientes_de_paciente(paciente_id):
        if _normalizar_especialidad(orm.especialidad_destino) != objetivo:
            continue
        if not _a_dominio(orm).esta_vigente(ahora):
            continue
        return completar_derivacion(db, orm.id, cita_id)
    return None


def expirar_vencidas(db: Session, ahora: datetime | None = None) -> int:
    """Expira las derivaciones pendientes cuyo plazo ya venció. Devuelve cuántas."""
    repo = RepositorioDerivaciones(db)
    expiradas = 0
    for orm in repo.listar_pendientes():
        deriv_dom = _a_dominio(orm)
        if deriv_dom.verificar_y_expirar_si_corresponde(ahora):
            orm.estado = deriv_dom.estado
            expiradas += 1
    if expiradas:
        db.commit()
    return expiradas


def listar_derivaciones_de_paciente(db: Session, paciente_id: int) -> list[DerivacionORM]:
    return RepositorioDerivaciones(db).listar_de_paciente(paciente_id)


def listar_pendientes_de_medico(db: Session, medico_id: int) -> list[DerivacionORM]:
    return RepositorioDerivaciones(db).listar_pendientes_de_medico(medico_id)
