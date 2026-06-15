"""Ciclo de vida de una cita médica (enunciado 3.1.1)."""

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

# Estados desde los que puede transicionarse cada estado.
_TRANSICIONES: dict[EstadoCita, frozenset[EstadoCita]] = {
    EstadoCita.PENDIENTE:  frozenset({EstadoCita.CONFIRMADA, EstadoCita.CANCELADA, EstadoCita.REAGENDADA}),
    EstadoCita.CONFIRMADA: frozenset({EstadoCita.CANCELADA, EstadoCita.COMPLETADA, EstadoCita.NO_ASISTIO, EstadoCita.REAGENDADA}),
    EstadoCita.CANCELADA:  frozenset(),
    EstadoCita.REAGENDADA: frozenset(),
    EstadoCita.COMPLETADA: frozenset(),
    EstadoCita.NO_ASISTIO: frozenset(),
}

# Citas en estos estados bloquean la agenda del médico.
ESTADOS_ACTIVOS = frozenset({EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA})


@dataclass
class Cita:
    """Representa una cita médica y su ciclo de vida."""

    id: UUID
    paciente_id: int   # RUN_usuario del paciente
    medico_id: int     # RUN_usuario del médico
    especialidad: str
    inicio: datetime
    fin: datetime
    estado: EstadoCita
    motivo: str
    creada_en: datetime

    notas: Optional[str] = field(default=None)
    reagendada_desde_id: Optional[UUID] = field(default=None)
    reagendada_hacia_id: Optional[UUID] = field(default=None)

    @classmethod
    def crear(
        cls,
        paciente_id: int,
        medico_id: int,
        especialidad: str,
        inicio: datetime,
        duracion_minutos: int = 30,
        motivo: str = "",
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """Crea y valida una nueva cita en estado PENDIENTE."""
        if duracion_minutos <= 0:
            raise ValueError(f"La duración debe ser positiva. Se recibió: {duracion_minutos} minutos.")

        referencia = ahora if ahora is not None else datetime.now(tz=inicio.tzinfo)

        if inicio <= referencia:
            raise CitaEnPasadoError(
                f"No se puede agendar una cita en el pasado. Inicio solicitado: {inicio.isoformat()}"
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

    def confirmar(self) -> None:
        self._transicionar(EstadoCita.CONFIRMADA)

    def cancelar(self) -> None:
        self._transicionar(EstadoCita.CANCELADA)

    def completar(self) -> None:
        self._transicionar(EstadoCita.COMPLETADA)

    def marcar_no_asistio(self) -> None:
        self._transicionar(EstadoCita.NO_ASISTIO)

    def reagendar(
        self,
        nueva_inicio: datetime,
        duracion_minutos: int = 30,
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """Marca esta cita como REAGENDADA y devuelve la nueva cita creada."""
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

    def se_solapa_con(self, otra: Cita) -> bool:
        """True si esta cita se superpone en horario con otra del mismo médico."""
        if self.medico_id != otra.medico_id:
            return False
        if self.estado not in ESTADOS_ACTIVOS or otra.estado not in ESTADOS_ACTIVOS:
            return False
        return self.inicio < otra.fin and otra.inicio < self.fin

    def validar_no_solapa(self, citas_existentes: list[Cita]) -> None:
        """Lanza ConflictoDeAgenda si hay solapamiento con alguna cita existente."""
        for existente in citas_existentes:
            if existente.id == self.id:
                continue
            if self.se_solapa_con(existente):
                raise ConflictoDeAgenda(
                    f"Conflicto de agenda: {self.inicio.isoformat()} – {self.fin.isoformat()} "
                    f"se superpone con la cita {existente.id} "
                    f"({existente.inicio.isoformat()} – {existente.fin.isoformat()})."
                )

    @property
    def duracion_minutos(self) -> int:
        return int((self.fin - self.inicio).total_seconds() / 60)

    @property
    def esta_activa(self) -> bool:
        return self.estado in ESTADOS_ACTIVOS

    def _transicionar(self, nuevo_estado: EstadoCita) -> None:
        permitidos = _TRANSICIONES.get(self.estado, frozenset())
        if nuevo_estado not in permitidos:
            raise TransicionEstadoInvalida(
                f"No se puede cambiar el estado de '{self.estado.value}' a '{nuevo_estado.value}'."
            )
        self.estado = nuevo_estado

    def __repr__(self) -> str:
        return (
            f"Cita(id={self.id}, paciente_run={self.paciente_id}, medico_run={self.medico_id}, "
            f"inicio={self.inicio.isoformat()}, fin={self.fin.isoformat()}, estado={self.estado.value})"
        )
