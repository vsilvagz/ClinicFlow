"""Derivación de pacientes entre especialidades o profesionales."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from app.backend.domain.enums import EstadoDerivacion
from app.backend.domain.errores import DerivacionExpirada, TransicionEstadoInvalida

# Transiciones válidas desde cada estado
_TRANSICIONES: dict[EstadoDerivacion, frozenset[EstadoDerivacion]] = {
    EstadoDerivacion.PENDIENTE: frozenset({
        EstadoDerivacion.ACEPTADA,
        EstadoDerivacion.RECHAZADA,
        EstadoDerivacion.EXPIRADA,
    }),
    EstadoDerivacion.ACEPTADA: frozenset({
        EstadoDerivacion.COMPLETADA,
        EstadoDerivacion.EXPIRADA,
    }),
    EstadoDerivacion.RECHAZADA: frozenset(),
    EstadoDerivacion.COMPLETADA: frozenset(),
    EstadoDerivacion.EXPIRADA: frozenset(),
}

DIAS_VIGENCIA_DEFAULT = 30


@dataclass
class Derivacion:
    """
    Representa una derivación médica hacia otra especialidad o profesional.

    Ciclo de vida:
        PENDIENTE → ACEPTADA → COMPLETADA
        PENDIENTE → RECHAZADA
        PENDIENTE | ACEPTADA → EXPIRADA

    Una derivación ACEPTADA habilita al paciente para agendar una cita en la
    especialidad destino (equivalente a tener la especialidad en
    Paciente._derivaciones_especialidades_permitidas).
    """

    id: UUID
    paciente_id: UUID
    medico_origen_id: UUID
    especialidad_destino: str
    motivo: str
    estado: EstadoDerivacion
    creada_en: datetime
    expira_en: datetime
    medico_destino_id: Optional[UUID] = field(default=None)
    cita_resultante_id: Optional[UUID] = field(default=None)
    notas: Optional[str] = field(default=None)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def crear(
        cls,
        paciente_id: UUID,
        medico_origen_id: UUID,
        especialidad_destino: str,
        motivo: str,
        dias_vigencia: int = DIAS_VIGENCIA_DEFAULT,
        medico_destino_id: Optional[UUID] = None,
        notas: Optional[str] = None,
        ahora: Optional[datetime] = None,
    ) -> Derivacion:
        """
        Crea una nueva derivación en estado PENDIENTE.

        Parameters
        ----------
        paciente_id:           UUID del paciente derivado.
        medico_origen_id:      UUID del médico que emite la derivación.
        especialidad_destino:  Especialidad a la que se deriva al paciente.
        motivo:                Motivo clínico de la derivación.
        dias_vigencia:         Días de validez antes de expirar (por defecto 30).
        medico_destino_id:     UUID del médico destino específico (opcional).
        notas:                 Observaciones clínicas adicionales (opcional).
        ahora:                 Referencia temporal; si se omite usa datetime.now()
                               (útil para testing).

        Raises
        ------
        ValueError  Si dias_vigencia no es positivo o especialidad_destino está vacía.
        """
        if dias_vigencia <= 0:
            raise ValueError(
                f"La vigencia debe ser un número positivo de días, se recibió {dias_vigencia}."
            )
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

    # ------------------------------------------------------------------
    # Transiciones de estado
    # ------------------------------------------------------------------

    def aceptar(self, ahora: Optional[datetime] = None) -> None:
        """
        El paciente acepta la derivación y queda habilitado para agendar.

        Raises
        ------
        DerivacionExpirada        Si la derivación ya venció.
        TransicionEstadoInvalida  Si el estado actual no permite aceptar.
        """
        self._verificar_vigencia(ahora)
        self._transicionar(EstadoDerivacion.ACEPTADA)

    def rechazar(self) -> None:
        """
        El paciente rechaza la derivación (PENDIENTE → RECHAZADA).

        Raises
        ------
        TransicionEstadoInvalida  Si el estado actual no permite rechazar.
        """
        self._transicionar(EstadoDerivacion.RECHAZADA)

    def completar(self, cita_id: UUID) -> None:
        """
        Registra que el paciente agendó una cita gracias a esta derivación.

        Parameters
        ----------
        cita_id:  UUID de la cita resultante.

        Raises
        ------
        TransicionEstadoInvalida  Si el estado actual no permite completar.
        """
        self._transicionar(EstadoDerivacion.COMPLETADA)
        self.cita_resultante_id = cita_id

    def expirar(self) -> None:
        """
        Marca la derivación como expirada por vencimiento de plazo.

        Raises
        ------
        TransicionEstadoInvalida  Si el estado actual no permite expirar.
        """
        self._transicionar(EstadoDerivacion.EXPIRADA)

    # ------------------------------------------------------------------
    # Reglas de negocio
    # ------------------------------------------------------------------

    def esta_vigente(self, ahora: Optional[datetime] = None) -> bool:
        """True si la derivación no ha vencido y está en un estado activo."""
        referencia = ahora if ahora is not None else datetime.now()
        activos = {EstadoDerivacion.PENDIENTE, EstadoDerivacion.ACEPTADA}
        return self.estado in activos and referencia < self.expira_en

    def puede_agendar(self, ahora: Optional[datetime] = None) -> bool:
        """True si el paciente puede usar esta derivación para agendar una cita."""
        return self.estado == EstadoDerivacion.ACEPTADA and self.esta_vigente(ahora)

    def verificar_y_expirar_si_corresponde(self, ahora: Optional[datetime] = None) -> bool:
        """
        Revisa si la derivación venció y la expira automáticamente si corresponde.

        Returns True si se expiró en esta llamada, False en caso contrario.
        Útil para ser invocado periódicamente por un servicio de background.
        """
        referencia = ahora if ahora is not None else datetime.now()
        activos = {EstadoDerivacion.PENDIENTE, EstadoDerivacion.ACEPTADA}
        if self.estado in activos and referencia >= self.expira_en:
            self.expirar()
            return True
        return False

    # ------------------------------------------------------------------
    # Propiedades calculadas
    # ------------------------------------------------------------------

    @property
    def dias_restantes(self) -> int:
        """Días que restan hasta el vencimiento (puede ser negativo si ya expiró)."""
        delta = self.expira_en - datetime.now()
        return delta.days

    @property
    def esta_activa(self) -> bool:
        """True si la derivación está en un estado que aún puede progresar."""
        return self.estado in {EstadoDerivacion.PENDIENTE, EstadoDerivacion.ACEPTADA}

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _verificar_vigencia(self, ahora: Optional[datetime] = None) -> None:
        referencia = ahora if ahora is not None else datetime.now()
        if referencia >= self.expira_en:
            raise DerivacionExpirada(
                f"La derivación {self.id} expiró el {self.expira_en.isoformat()}."
            )

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
