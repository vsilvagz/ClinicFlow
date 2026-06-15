"""Derivación de pacientes entre especialidades o profesionales."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from app.backend.domain.enums import EstadoDerivacion
from app.backend.domain.errores import TransicionEstadoInvalida

# Flujo: médico crea derivación (PENDIENTE) → paciente agenda cita en especialidad destino
# → se llama completar() (COMPLETADA). Si el plazo vence sin que agende → EXPIRADA.

_TRANSICIONES: dict[EstadoDerivacion, frozenset[EstadoDerivacion]] = {
    EstadoDerivacion.PENDIENTE:  frozenset({EstadoDerivacion.COMPLETADA, EstadoDerivacion.EXPIRADA}),
    EstadoDerivacion.COMPLETADA: frozenset(),
    EstadoDerivacion.EXPIRADA:   frozenset(),
}

DIAS_VIGENCIA_DEFAULT = 30


@dataclass
class Derivacion:
    """Derivación médica hacia otra especialidad o profesional."""

    id: UUID
    paciente_id: int
    medico_origen_id: int
    especialidad_destino: str
    motivo: str
    estado: EstadoDerivacion
    creada_en: datetime
    expira_en: datetime

    medico_destino_id: Optional[int]  = field(default=None)
    cita_resultante_id: Optional[UUID] = field(default=None)
    notas: Optional[str] = field(default=None)

    @classmethod
    def crear(
        cls,
        paciente_id: int,
        medico_origen_id: int,
        especialidad_destino: str,
        motivo: str,
        dias_vigencia: int = DIAS_VIGENCIA_DEFAULT,
        medico_destino_id: Optional[int] = None,
        notas: Optional[str] = None,
        ahora: Optional[datetime] = None,
    ) -> Derivacion:
        """Crea una nueva derivación en estado PENDIENTE."""
        if dias_vigencia <= 0:
            raise ValueError(f"La vigencia debe ser positiva, se recibió {dias_vigencia}.")

        especialidad_destino = especialidad_destino.strip()
        if not especialidad_destino:
            raise ValueError("La especialidad destino no puede estar vacía.")

        referencia = ahora if ahora is not None else datetime.now()

        return cls(
            id=uuid4(),
            paciente_id=paciente_id,
            medico_origen_id=medico_origen_id,
            especialidad_destino=especialidad_destino,
            motivo=motivo,
            estado=EstadoDerivacion.PENDIENTE,
            creada_en=referencia,
            expira_en=referencia + timedelta(days=dias_vigencia),
            medico_destino_id=medico_destino_id,
            notas=notas,
        )

    def completar(self, cita_id: UUID) -> None:
        """El paciente agendó usando esta derivación: PENDIENTE → COMPLETADA."""
        self._transicionar(EstadoDerivacion.COMPLETADA)
        self.cita_resultante_id = cita_id

    def expirar(self) -> None:
        """El plazo venció sin que el paciente agendara: PENDIENTE → EXPIRADA."""
        self._transicionar(EstadoDerivacion.EXPIRADA)

    def esta_vigente(self, ahora: Optional[datetime] = None) -> bool:
        """True si la derivación sigue activa y no ha vencido."""
        referencia = ahora if ahora is not None else datetime.now()
        return self.estado == EstadoDerivacion.PENDIENTE and referencia < self.expira_en

    def verificar_y_expirar_si_corresponde(self, ahora: Optional[datetime] = None) -> bool:
        """Expira la derivación si su plazo venció. Devuelve True si se expiró ahora."""
        referencia = ahora if ahora is not None else datetime.now()
        if self.estado == EstadoDerivacion.PENDIENTE and referencia >= self.expira_en:
            self.expirar()
            return True
        return False

    @property
    def dias_restantes(self) -> int:
        """Días que restan hasta el vencimiento (negativo si ya expiró)."""
        return (self.expira_en - datetime.now()).days

    @property
    def esta_activa(self) -> bool:
        """True si la derivación aún puede progresar."""
        return self.estado == EstadoDerivacion.PENDIENTE

    def _transicionar(self, nuevo_estado: EstadoDerivacion) -> None:
        permitidos = _TRANSICIONES.get(self.estado, frozenset())
        if nuevo_estado not in permitidos:
            raise TransicionEstadoInvalida(
                f"No se puede pasar de '{self.estado.value}' a '{nuevo_estado.value}'"
            )
        self.estado = nuevo_estado

    def __repr__(self) -> str:
        return (
            f"Derivacion(id={self.id}, paciente={self.paciente_id}, "
            f"especialidad='{self.especialidad_destino}', estado={self.estado.value}, "
            f"expira={self.expira_en.isoformat()})"
        )
