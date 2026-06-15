"""Agenda médica: disponibilidad, bloqueos y suspensiones."""

# Permite usar tipos de la propia clase dentro de sus métodos sin errores de Python.
from __future__ import annotations

# dataclass: genera el constructor __init__ automáticamente según los atributos declarados.
from dataclasses import dataclass

# date: solo la fecha (sin hora), ej: 2026-06-14.
# datetime: fecha y hora juntas, ej: 2026-06-14 10:30.
# time: solo la hora, ej: 10:30.
# timedelta: una duración, ej: 30 minutos.
from datetime import date, datetime, time, timedelta

# Importamos la clase Cita para poder guardar citas dentro de la agenda.
from app.backend.domain.citas import Cita

# Importamos los errores que lanzaremos si algo no está permitido.
from app.backend.domain.errores import AgendaSuspendida, ConflictoDeAgenda, HorarioNoDisponible


# ──────────────────────────────────────────────────────────────────────────────
# BloqueHorario: representa un turno semanal recurrente del médico.
# Ej: "los lunes de 09:00 a 13:00".
# ──────────────────────────────────────────────────────────────────────────────

@dataclass  # genera __init__ automáticamente con los tres atributos de abajo
class BloqueHorario:
    """Franja semanal recurrente de disponibilidad del médico."""

    dia_semana: int   # Día de la semana como número: 0=lunes, 1=martes, ..., 6=domingo.
    hora_inicio: time # Hora en que empieza el turno de atención, ej: 09:00.
    hora_fin: time    # Hora en que termina el turno de atención, ej: 13:00.

    def cubre(self, inicio: datetime, fin: datetime) -> bool:
        """Devuelve True si el intervalo [inicio, fin) cae dentro de este bloque."""
        if inicio.weekday() != self.dia_semana:  # Si el día de la semana no coincide, no cubre.
            return False
        # Verifica que la hora de inicio sea igual o después del turno, y que el fin sea antes del cierre.
        return inicio.time() >= self.hora_inicio and fin.time() <= self.hora_fin


# ──────────────────────────────────────────────────────────────────────────────
# Bloqueo: un período puntual en que el médico no puede recibir citas NUEVAS,
# pero las citas que ya existían antes del bloqueo no se cancelan.
# Ej: "el martes 15 de julio de 11:00 a 12:00 tengo una reunión".
# ──────────────────────────────────────────────────────────────────────────────

@dataclass  # genera __init__ automáticamente con inicio, fin y motivo
class Bloqueo:
    """Bloqueo puntual de un intervalo específico sin afectar citas existentes."""

    inicio: datetime  # Fecha y hora en que empieza el bloqueo.
    fin: datetime     # Fecha y hora en que termina el bloqueo.
    motivo: str = ""  # Razón del bloqueo (opcional, por defecto vacío).

    def se_solapa_con(self, inicio: datetime, fin: datetime) -> bool:
        """Devuelve True si el intervalo [inicio, fin) choca con este bloqueo."""
        # Hay choque si el bloqueo empieza antes de que el intervalo termine,
        # Y el intervalo empieza antes de que el bloqueo termine.
        return self.inicio < fin and inicio < self.fin


# ──────────────────────────────────────────────────────────────────────────────
# Suspension: un período en que el médico suspende TODA su agenda.
# A diferencia del Bloqueo, la suspensión SÍ cancela las citas activas
# que ya estaban agendadas dentro del período.
# Ej: "el médico estará de vacaciones del 1 al 15 de agosto".
# ──────────────────────────────────────────────────────────────────────────────

@dataclass  # genera __init__ automáticamente
class Suspension:
    """Suspensión completa de la agenda durante un período."""

    inicio: datetime  # Fecha y hora en que empieza la suspensión.
    fin: datetime     # Fecha y hora en que termina la suspensión.
    motivo: str = ""  # Razón de la suspensión (opcional).

    def se_solapa_con(self, inicio: datetime, fin: datetime) -> bool:
        """Devuelve True si el intervalo [inicio, fin) cae dentro de la suspensión."""
        # Misma lógica de solapamiento que en Bloqueo.
        return self.inicio < fin and inicio < self.fin


# ──────────────────────────────────────────────────────────────────────────────
# Agenda: el objeto principal que gestiona toda la disponibilidad del médico.
# Contiene la lista de horarios, bloqueos, suspensiones y citas.
# No usa @dataclass porque tiene lógica de negocio más compleja.
# ──────────────────────────────────────────────────────────────────────────────

class Agenda:
    """
    Gestiona la disponibilidad de un médico: horarios, bloqueos y suspensiones.

    Responsabilidades:
    - Definir horarios de atención recurrentes por día de semana.
    - Registrar bloqueos puntuales y suspensiones completas.
    - Verificar disponibilidad antes de registrar una cita.
    - Listar slots libres en una fecha.
    - Al suspender, cancelar automáticamente las citas activas afectadas.
    """

    def __init__(
        self,
        duracion_slot_minutos: int = 30,      # Duración de cada turno en minutos (30 por defecto).
        capacidad_maxima_dia: int | None = None, # Límite de citas por día (None = sin límite).
    ):
        if duracion_slot_minutos <= 0:
            raise ValueError("La duración del slot debe ser mayor a 0.")
        else:
            self._duracion_slot = duracion_slot_minutos  # Guardamos la duración del slot como atributo privado.
        self._capacidad_maxima_dia = capacidad_maxima_dia  # Guardamos el límite diario (puede ser None).
        self._horarios: list[BloqueHorario] = []   # Lista de turnos semanales recurrentes.
        self._bloqueos: list[Bloqueo] = []         # Lista de bloqueos puntuales.
        self._suspensiones: list[Suspension] = []  # Lista de suspensiones completas.
        self._citas: list[Cita] = []               # Lista de citas registradas en esta agenda.

    # ── Propiedades ────────────────────────────────────────────────────────────

    @property  # convierte este método en un atributo de solo lectura
    def duracion_slot_minutos(self) -> int:
        return self._duracion_slot  # Devuelve la duración de cada slot configurada.

    # ── Configuración de horarios ──────────────────────────────────────────────

    def agregar_horario(self, bloque: BloqueHorario) -> None:
        """Añade una franja horaria recurrente a la agenda."""
        self._horarios.append(bloque)  # Agrega el bloque a la lista de horarios del médico.

    def bloquear(self, inicio: datetime, fin: datetime, motivo: str = "") -> Bloqueo:
        """Bloquea un intervalo puntual sin cancelar citas ya agendadas."""
        bloqueo = Bloqueo(inicio=inicio, fin=fin, motivo=motivo)  # Crea el objeto Bloqueo.
        self._bloqueos.append(bloqueo)  # Lo agrega a la lista de bloqueos.
        return bloqueo  # Devuelve el bloqueo creado para que quien llame lo pueda usar.

    def suspender(
        self, inicio: datetime, fin: datetime, motivo: str = ""
    ) -> tuple[Suspension, list[Cita]]:
        """
        Suspende la agenda en el período indicado y cancela las citas activas afectadas.
        Devuelve la suspensión creada y la lista de citas que fueron canceladas,
        para que el servicio pueda notificar a los pacientes.
        """
        suspension = Suspension(inicio=inicio, fin=fin, motivo=motivo)  # Crea la suspensión.
        self._suspensiones.append(suspension)  # La agrega a la lista de suspensiones.

        canceladas: list[Cita] = []  # Lista vacía donde iremos guardando las citas que cancelemos.
        for cita in self._citas:  # Recorremos todas las citas registradas en la agenda.
            # Si la cita está activa Y se superpone con el período suspendido, la cancelamos.
            if cita.esta_activa and suspension.se_solapa_con(cita.inicio, cita.fin):
                cita.cancelar()           # Cambia el estado de la cita a CANCELADA.
                canceladas.append(cita)   # La guardamos en la lista de canceladas para notificar.

        return suspension, canceladas  # Devolvemos la suspensión y las citas canceladas.

    # ── Gestión de citas ───────────────────────────────────────────────────────

    def agregar_cita(self, cita: Cita) -> None:
        """
        Registra una cita en la agenda validando todas las restricciones.
        Lanza un error si el horario no está disponible, hay suspensión, bloqueo,
        solapamiento con otra cita, o se superó el límite diario.
        """
        self._validar_en_horario(cita.inicio, cita.fin)   # ¿Cae dentro del horario del médico?
        self._validar_sin_suspension(cita.inicio, cita.fin)  # ¿Hay suspensión en ese período?
        self._validar_sin_bloqueo(cita.inicio, cita.fin)    # ¿Hay bloqueo puntual en ese horario?
        cita.validar_no_solapa(self._citas)                  # ¿Se superpone con otra cita activa?
        self._validar_capacidad(cita.inicio.date())          # ¿Se llegó al límite de citas del día?
        self._citas.append(cita)                             # Si todo está bien, la registramos.

    def citas_del_dia(self, fecha: date) -> list[Cita]:
        """Devuelve todas las citas (de cualquier estado) de una fecha específica."""
        # Filtramos la lista completa y retornamos solo las que empiezan en 'fecha'.
        return [c for c in self._citas if c.inicio.date() == fecha]

    def citas_activas(self) -> list[Cita]:
        """Devuelve solo las citas que están en estado PENDIENTE o CONFIRMADA."""
        return [c for c in self._citas if c.esta_activa]  # Usa la propiedad esta_activa de Cita.

    # ── Disponibilidad ─────────────────────────────────────────────────────────

    def esta_disponible(self, inicio: datetime, duracion_minutos: int | None = None) -> bool:
        """Devuelve True si el slot [inicio, inicio+duración) está completamente libre."""
        duracion = duracion_minutos or self._duracion_slot  # Usa la duración dada o la del slot.
        fin = inicio + timedelta(minutes=duracion)          # Calcula cuándo terminaría la cita.

        try:
            # Intentamos pasar las tres validaciones. Si alguna falla, capturamos el error abajo.
            self._validar_en_horario(inicio, fin)
            self._validar_sin_suspension(inicio, fin)
            self._validar_sin_bloqueo(inicio, fin)
        except (HorarioNoDisponible, AgendaSuspendida, ConflictoDeAgenda):
            return False  # Si cualquier validación falla, el slot NO está disponible.

        # Comprobamos si alguna cita activa ya ocupa ese horario.
        if any(c.esta_activa and c.inicio < fin and inicio < c.fin for c in self._citas):
            return False  # Hay una cita activa que se superpone: no está disponible.

        # Si hay límite diario, contamos cuántas citas activas hay ese día.
        if self._capacidad_maxima_dia is not None:
            activas_ese_dia = sum(
                1 for c in self._citas
                if c.esta_activa and c.inicio.date() == inicio.date()
            )
            if activas_ese_dia >= self._capacidad_maxima_dia:
                return False  # Ya se alcanzó el límite de citas del día.

        return True  # Si pasó todas las verificaciones, el slot sí está disponible.

    def slots_disponibles(self, fecha: date) -> list[datetime]:
        """Lista todas las horas libres en una fecha según los horarios definidos."""
        slots: list[datetime] = []  # Lista vacía donde iremos guardando los slots libres.
        for bloque in self._horarios:  # Recorremos cada turno semanal registrado.
            if bloque.dia_semana != fecha.weekday():  # Si el día no coincide, saltamos.
                continue
            # Empezamos desde la hora de inicio del turno.
            cursor = datetime.combine(fecha, bloque.hora_inicio)
            # Hasta la hora de fin del turno.
            fin_bloque = datetime.combine(fecha, bloque.hora_fin)
            # Avanzamos de slot en slot mientras quepan dentro del turno.
            while cursor + timedelta(minutes=self._duracion_slot) <= fin_bloque:
                if self.esta_disponible(cursor):  # Si el slot está libre, lo agregamos.
                    slots.append(cursor)
                cursor += timedelta(minutes=self._duracion_slot)  # Avanzamos al siguiente slot.
        return slots  # Devolvemos la lista de horarios disponibles.

    # ── Validaciones internas (privadas) ──────────────────────────────────────

    def _validar_en_horario(self, inicio: datetime, fin: datetime) -> None:
        # Verifica que el intervalo esté cubierto por al menos un BloqueHorario.
        if not any(b.cubre(inicio, fin) for b in self._horarios):
            raise HorarioNoDisponible(  # Si ningún bloque lo cubre, lanzamos el error.
                f"El slot {inicio.isoformat()} – {fin.isoformat()} "
                "no corresponde a ningún horario de atención definido."
            )

    def _validar_sin_suspension(self, inicio: datetime, fin: datetime) -> None:
        for s in self._suspensiones:  # Recorremos todas las suspensiones activas.
            if s.se_solapa_con(inicio, fin):  # Si alguna se superpone con el horario pedido...
                raise AgendaSuspendida(       # ...lanzamos el error de agenda suspendida.
                    f"La agenda está suspendida entre {s.inicio.isoformat()} "
                    f"y {s.fin.isoformat()}. Motivo: {s.motivo}"
                )

    def _validar_sin_bloqueo(self, inicio: datetime, fin: datetime) -> None:
        for b in self._bloqueos:  # Recorremos todos los bloqueos puntuales.
            if b.se_solapa_con(inicio, fin):  # Si alguno se superpone con el horario pedido...
                raise ConflictoDeAgenda(      # ...lanzamos el error de conflicto de agenda.
                    f"El horario {inicio.isoformat()} – {fin.isoformat()} "
                    f"está bloqueado. Motivo: {b.motivo}"
                )

    def _validar_capacidad(self, fecha: date) -> None:
        if self._capacidad_maxima_dia is None:  # Si no hay límite configurado, no hacemos nada.
            return
        # Contamos cuántas citas activas hay para ese día.
        activas = sum(
            1 for c in self._citas
            if c.esta_activa and c.inicio.date() == fecha
        )
        if activas >= self._capacidad_maxima_dia:  # Si ya se llegó al límite...
            raise ConflictoDeAgenda(               # ...lanzamos el error.
                f"Se alcanzó el límite de {self._capacidad_maxima_dia} "
                f"citas para el día {fecha}."
            )
