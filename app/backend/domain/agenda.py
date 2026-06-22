"""Agenda médica: disponibilidad, bloqueos y suspensiones (enunciado 3.1.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.backend.domain.citas import Cita
from app.backend.domain.errores import AgendaSuspendida, ConflictoDeAgenda, HorarioNoDisponible


@dataclass
class BloqueHorario:
    """Franja semanal recurrente de disponibilidad del médico (0=lunes … 6=domingo)."""

    dia_semana: int
    hora_inicio: time
    hora_fin: time

    def cubre(self, inicio: datetime, fin: datetime) -> bool:
        if inicio.weekday() != self.dia_semana:
            return False
        return inicio.time() >= self.hora_inicio and fin.time() <= self.hora_fin


@dataclass
class Bloqueo:
    """Período en que el médico no acepta citas nuevas, sin cancelar las existentes."""

    inicio: datetime
    fin: datetime
    motivo: str = ""

    def se_solapa_con(self, inicio: datetime, fin: datetime) -> bool:
        return self.inicio < fin and inicio < self.fin


@dataclass
class Suspension:
    """Suspensión completa de la agenda: cancela las citas activas del período."""

    inicio: datetime
    fin: datetime
    motivo: str = ""

    def se_solapa_con(self, inicio: datetime, fin: datetime) -> bool:
        return self.inicio < fin and inicio < self.fin


class Agenda:
    """
    Gestiona la disponibilidad de un médico.
    Responsabilidades: horarios recurrentes, bloqueos, suspensiones y citas.
    """

    def __init__(self, duracion_slot_minutos: int = 30, capacidad_maxima_dia: int | None = None):
        if duracion_slot_minutos <= 0:
            raise ValueError("La duración del slot debe ser mayor a 0.")
        self._duracion_slot = duracion_slot_minutos
        self._capacidad_maxima_dia = capacidad_maxima_dia
        self._horarios: list[BloqueHorario] = []
        self._bloqueos: list[Bloqueo] = []
        self._suspensiones: list[Suspension] = []
        self._citas: list[Cita] = []

    @property
    def duracion_slot_minutos(self) -> int:
        return self._duracion_slot

    def agregar_horario(self, bloque: BloqueHorario) -> None:
        self._horarios.append(bloque)

    def bloquear(self, inicio: datetime, fin: datetime, motivo: str = "") -> Bloqueo:
        bloqueo = Bloqueo(inicio=inicio, fin=fin, motivo=motivo)
        self._bloqueos.append(bloqueo)
        return bloqueo

    def suspender(self, inicio: datetime, fin: datetime, motivo: str = "") -> tuple[Suspension, list[Cita]]:
        """Suspende la agenda y cancela las citas activas afectadas. Devuelve las citas canceladas."""
        suspension = Suspension(inicio=inicio, fin=fin, motivo=motivo)
        self._suspensiones.append(suspension)

        canceladas: list[Cita] = []
        for cita in self._citas:
            if cita.esta_activa and suspension.se_solapa_con(cita.inicio, cita.fin):
                cita.cancelar()
                canceladas.append(cita)

        return suspension, canceladas

    def agregar_cita(self, cita: Cita) -> None:
        """Registra una cita tras validar horario, suspensiones, bloqueos, solapamiento y capacidad."""
        self._validar_en_horario(cita.inicio, cita.fin)
        self._validar_sin_suspension(cita.inicio, cita.fin)
        self._validar_sin_bloqueo(cita.inicio, cita.fin)
        cita.validar_no_solapa(self._citas)
        self._validar_capacidad(cita.inicio.date())
        self._citas.append(cita)

    def cargar_citas(self, citas: list[Cita]) -> None:
        """Rehidrata citas ya validadas desde la persistencia, sin volver a validar.

        Lo usa la capa de servicios al reconstruir una agenda desde la base de
        datos: esas citas ya superaron las validaciones cuando se crearon, así que
        solo se incorporan para poder consultar disponibilidad y slots libres.
        """
        self._citas.extend(citas)

    def citas_del_dia(self, fecha: date) -> list[Cita]:
        return [c for c in self._citas if c.inicio.date() == fecha]

    def citas_activas(self) -> list[Cita]:
        return [c for c in self._citas if c.esta_activa]

    def esta_disponible(self, inicio: datetime, duracion_minutos: int | None = None) -> bool:
        duracion = duracion_minutos or self._duracion_slot
        fin = inicio + timedelta(minutes=duracion)

        try:
            self._validar_en_horario(inicio, fin)
            self._validar_sin_suspension(inicio, fin)
            self._validar_sin_bloqueo(inicio, fin)
        except (HorarioNoDisponible, AgendaSuspendida, ConflictoDeAgenda):
            return False

        if any(c.esta_activa and c.inicio < fin and inicio < c.fin for c in self._citas):
            return False

        if self._capacidad_maxima_dia is not None:
            activas_ese_dia = sum(
                1 for c in self._citas
                if c.esta_activa and c.inicio.date() == inicio.date()
            )
            if activas_ese_dia >= self._capacidad_maxima_dia:
                return False

        return True

    def slots_disponibles(self, fecha: date) -> list[datetime]:
        """Lista todas las horas libres en una fecha según los horarios definidos."""
        slots: list[datetime] = []
        for bloque in self._horarios:
            if bloque.dia_semana != fecha.weekday():
                continue
            cursor = datetime.combine(fecha, bloque.hora_inicio)
            fin_bloque = datetime.combine(fecha, bloque.hora_fin)
            while cursor + timedelta(minutes=self._duracion_slot) <= fin_bloque:
                if self.esta_disponible(cursor):
                    slots.append(cursor)
                cursor += timedelta(minutes=self._duracion_slot)
        return slots

    def _validar_en_horario(self, inicio: datetime, fin: datetime) -> None:
        if not any(b.cubre(inicio, fin) for b in self._horarios):
            raise HorarioNoDisponible(
                f"El slot {inicio.isoformat()} – {fin.isoformat()} no corresponde a ningún horario de atención."
            )

    def _validar_sin_suspension(self, inicio: datetime, fin: datetime) -> None:
        for s in self._suspensiones:
            if s.se_solapa_con(inicio, fin):
                raise AgendaSuspendida(
                    f"La agenda está suspendida entre {s.inicio.isoformat()} y {s.fin.isoformat()}. Motivo: {s.motivo}"
                )

    def _validar_sin_bloqueo(self, inicio: datetime, fin: datetime) -> None:
        for b in self._bloqueos:
            if b.se_solapa_con(inicio, fin):
                raise ConflictoDeAgenda(
                    f"El horario {inicio.isoformat()} – {fin.isoformat()} está bloqueado. Motivo: {b.motivo}"
                )

    def _validar_capacidad(self, fecha: date) -> None:
        if self._capacidad_maxima_dia is None:
            return
        activas = sum(1 for c in self._citas if c.esta_activa and c.inicio.date() == fecha)
        if activas >= self._capacidad_maxima_dia:
            raise ConflictoDeAgenda(
                f"Se alcanzó el límite de {self._capacidad_maxima_dia} citas para el día {fecha}."
            )
