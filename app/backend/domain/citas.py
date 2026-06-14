"""Entidad Cita y sus operaciones de estado."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from app.backend.domain.enums import EstadoCita
from app.backend.domain.errores import (
    CitaEnPasadoError,
    ConflictoDeAgenda,
    TransicionEstadoInvalida,
)

# Transiciones válidas desde cada estado
_TRANSICIONES: dict[EstadoCita, frozenset[EstadoCita]] = {
    EstadoCita.PENDIENTE: frozenset({
        EstadoCita.CONFIRMADA,
        EstadoCita.CANCELADA,
        EstadoCita.REAGENDADA,
    }),
    EstadoCita.CONFIRMADA: frozenset({
        EstadoCita.CANCELADA,
        EstadoCita.COMPLETADA,
        EstadoCita.NO_ASISTIO,
        EstadoCita.REAGENDADA,
    }),
    EstadoCita.CANCELADA: frozenset(),
    EstadoCita.REAGENDADA: frozenset(),
    EstadoCita.COMPLETADA: frozenset(),
    EstadoCita.NO_ASISTIO: frozenset(),
}

# Estados que se consideran "activos" (ocupan el horario del médico)
ESTADOS_ACTIVOS = frozenset({EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA})


@dataclass
class Cita:
    """
    Representa una cita médica con su ciclo de vida completo.

    Invariantes:
    - inicio < fin
    - estado sigue la máquina de estados definida en _TRANSICIONES
    - Una cita sólo puede reagendarse si su estado es PENDIENTE o CONFIRMADA
    """

    id: UUID
    paciente_id: UUID
    medico_id: UUID
    especialidad: str
    inicio: datetime
    fin: datetime
    estado: EstadoCita
    motivo: str
    creada_en: datetime
    notas: Optional[str] = field(default=None)
    reagendada_desde_id: Optional[UUID] = field(default=None)
    reagendada_hacia_id: Optional[UUID] = field(default=None)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def crear(
        cls,
        paciente_id: UUID,
        medico_id: UUID,
        especialidad: str,
        inicio: datetime,
        duracion_minutos: int = 30,
        motivo: str = "",
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """
        Crea una nueva cita en estado PENDIENTE.

        Parameters
        ----------
        paciente_id:       UUID del paciente.
        medico_id:         UUID del médico tratante.
        especialidad:      Nombre de la especialidad médica.
        inicio:            Fecha y hora de inicio de la cita (timezone-aware recomendado).
        duracion_minutos:  Duración en minutos (por defecto 30).
        motivo:            Motivo o descripción de la consulta.
        ahora:             Momento de referencia para la validación temporal
                           (útil para testing; si se omite usa datetime.now).

        Raises
        ------
        CitaEnPasadoError   Si ``inicio`` es anterior o igual al momento actual.
        ValueError          Si ``duracion_minutos`` no es positivo.
        """
        if duracion_minutos <= 0:
            raise ValueError(f"La duración debe ser un número positivo de minutos, se recibió {duracion_minutos}")

        referencia = ahora if ahora is not None else datetime.now(tz=inicio.tzinfo)
        if inicio <= referencia:
            raise CitaEnPasadoError(
                f"No se puede agendar una cita en el pasado: {inicio.isoformat()}"
            )

        return cls(
            id=uuid4(),
            paciente_id=paciente_id,
            medico_id=medico_id,
            especialidad=especialidad,
            inicio=inicio,
            fin=inicio + timedelta(minutes=duracion_minutos),
            estado=EstadoCita.PENDIENTE,
            motivo=motivo,
            creada_en=referencia,
        )

    # ------------------------------------------------------------------
    # Transiciones de estado
    # ------------------------------------------------------------------

    def confirmar(self) -> None:
        """Confirma la cita (PENDIENTE → CONFIRMADA)."""
        self._transicionar(EstadoCita.CONFIRMADA)

    def cancelar(self) -> None:
        """Cancela la cita (PENDIENTE|CONFIRMADA → CANCELADA)."""
        self._transicionar(EstadoCita.CANCELADA)

    def completar(self) -> None:
        """Marca la cita como completada (CONFIRMADA → COMPLETADA)."""
        self._transicionar(EstadoCita.COMPLETADA)

    def marcar_no_asistio(self) -> None:
        """Registra la inasistencia del paciente (CONFIRMADA → NO_ASISTIO)."""
        self._transicionar(EstadoCita.NO_ASISTIO)

    def reagendar(
        self,
        nueva_inicio: datetime,
        duracion_minutos: int = 30,
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """
        Cierra esta cita como REAGENDADA y devuelve la nueva cita en PENDIENTE.

        La nueva cita hereda paciente, médico, especialidad y motivo.
        Se registra el vínculo bidireccional entre ambas citas.

        Raises
        ------
        TransicionEstadoInvalida  Si el estado actual no permite reagendar.
        CitaEnPasadoError         Si ``nueva_inicio`` está en el pasado.
        ValueError                Si ``duracion_minutos`` no es positivo.
        """
        self._transicionar(EstadoCita.REAGENDADA)

        nueva = Cita.crear(
            paciente_id=self.paciente_id,
            medico_id=self.medico_id,
            especialidad=self.especialidad,
            inicio=nueva_inicio,
            duracion_minutos=duracion_minutos,
            motivo=self.motivo,
            ahora=ahora,
        )
        nueva.reagendada_desde_id = self.id
        self.reagendada_hacia_id = nueva.id
        return nueva

    # ------------------------------------------------------------------
    # Reglas de negocio
    # ------------------------------------------------------------------

    def se_solapa_con(self, otra: Cita) -> bool:
        """
        Indica si esta cita se solapa temporalmente con ``otra`` para el mismo médico.

        Sólo se consideran citas en estado PENDIENTE o CONFIRMADA.
        Una cita cancelada, reagendada, completada o de inasistencia no ocupa agenda.
        """
        if self.medico_id != otra.medico_id:
            return False
        if self.estado not in ESTADOS_ACTIVOS or otra.estado not in ESTADOS_ACTIVOS:
            return False
        return self.inicio < otra.fin and otra.inicio < self.fin

    def validar_no_solapa(self, citas_existentes: list[Cita]) -> None:
        """
        Lanza ConflictoDeAgenda si esta cita se solapa con alguna de las existentes.

        Parameters
        ----------
        citas_existentes:  Lista de citas activas del médico.

        Raises
        ------
        ConflictoDeAgenda  Si hay al menos un solapamiento.
        """
        for existente in citas_existentes:
            if existente.id != self.id and self.se_solapa_con(existente):
                raise ConflictoDeAgenda(
                    f"La cita solicitada ({self.inicio.isoformat()} – {self.fin.isoformat()}) "
                    f"se solapa con la cita {existente.id} "
                    f"({existente.inicio.isoformat()} – {existente.fin.isoformat()})"
                )

    # ------------------------------------------------------------------
    # Propiedades calculadas
    # ------------------------------------------------------------------

    @property
    def duracion_minutos(self) -> int:
        """Duración de la cita en minutos."""
        return int((self.fin - self.inicio).total_seconds() / 60)

    @property
    def esta_activa(self) -> bool:
        """True si la cita está en un estado que ocupa agenda."""
        return self.estado in ESTADOS_ACTIVOS

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _transicionar(self, nuevo_estado: EstadoCita) -> None:
        permitidos = _TRANSICIONES.get(self.estado, frozenset())
        if nuevo_estado not in permitidos:
            raise TransicionEstadoInvalida(
                f"No se puede pasar de '{self.estado.value}' a '{nuevo_estado.value}'"
            )
        self.estado = nuevo_estado

    def __repr__(self) -> str:
        return (
            f"Cita(id={self.id}, paciente={self.paciente_id}, "
            f"medico={self.medico_id}, inicio={self.inicio.isoformat()}, "
            f"estado={self.estado.value})"
        )
