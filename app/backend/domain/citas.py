"""
Módulo: citas.py
Responsabilidad (enunciado sección 3.1.1): gestionar el ciclo de vida de
una cita médica — crearla, confirmarla, cancelarla, reagendarla y validar
que no genere conflictos de agenda.
"""

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTACIONES
# Le decimos a Python qué herramientas necesitamos de otros archivos/módulos.
# ──────────────────────────────────────────────────────────────────────────────

# Permite usar el nombre 'Cita' dentro de la propia clase Cita sin errores.
# (Python normalmente no conoce una clase hasta terminar de leerla.)
from __future__ import annotations

# dataclass: decorador que genera __init__ automáticamente a partir de los
#            atributos declarados, evitando escribir self.x = x para cada uno.
# field:     permite configurar valores por defecto para atributos opcionales.
from dataclasses import dataclass, field

# datetime: representa una fecha+hora concreta, ej. 2026-06-14 10:30.
# timedelta: representa una duración, ej. 30 minutos.
from datetime import datetime, timedelta

# Optional[T] indica que un valor puede ser de tipo T o puede ser None.
from typing import Optional

# UUID: identificador único universal (código irrepetible de 128 bits).
# uuid4: función que genera un UUID aleatorio cada vez que se llama.
from uuid import UUID, uuid4

# EstadoCita: enumeración con los 6 estados posibles de una cita
# (definida en enums.py, exigida por el enunciado sección 3.1.1).
from app.backend.domain.enums import EstadoCita

# Errores de dominio propios del proyecto (definidos en errores.py).
from app.backend.domain.errores import (
    CitaEnPasadoError,        # Se lanza si el inicio de la cita ya pasó.
    ConflictoDeAgenda,        # Se lanza si dos citas del mismo médico se superponen.
    TransicionEstadoInvalida, # Se lanza si el cambio de estado no está permitido.
)


# ──────────────────────────────────────────────────────────────────────────────
# MÁQUINA DE ESTADOS
# Define QUÉ cambios de estado están permitidos (enunciado: "gestionar estados").
# Es como un mapa de carreteras: desde cada estado, a dónde puedes ir.
# ──────────────────────────────────────────────────────────────────────────────

# Diccionario: cada EstadoCita apunta al conjunto de estados a los que puede pasar.
# frozenset es un conjunto inmutable; no se puede modificar accidentalmente.
_TRANSICIONES: dict[EstadoCita, frozenset[EstadoCita]] = {

    # PENDIENTE: la cita fue creada pero aún no confirmada.
    # Puede confirmarse, cancelarse o reagendarse.
    EstadoCita.PENDIENTE: frozenset({
        EstadoCita.CONFIRMADA,
        EstadoCita.CANCELADA,
        EstadoCita.REAGENDADA,
    }),

    # CONFIRMADA: la cita fue aceptada por el médico/recepcionista.
    # Puede cancelarse, marcarse como realizada, reagendarse o registrar inasistencia.
    EstadoCita.CONFIRMADA: frozenset({
        EstadoCita.CANCELADA,
        EstadoCita.COMPLETADA,
        EstadoCita.NO_ASISTIO,
        EstadoCita.REAGENDADA,
    }),

    # Estados finales: una vez aquí, la cita no puede cambiar de estado.
    EstadoCita.CANCELADA:  frozenset(),  # Cita anulada definitivamente.
    EstadoCita.REAGENDADA: frozenset(),  # Esta cita fue reemplazada por una nueva.
    EstadoCita.COMPLETADA: frozenset(),  # La consulta se realizó con éxito.
    EstadoCita.NO_ASISTIO: frozenset(),  # El paciente no se presentó.
}

# Conjunto de estados que significan que la cita "ocupa" el horario del médico.
# Usado para detectar conflictos de agenda (enunciado: "evitar conflictos").
# Una cita CANCELADA, COMPLETADA, etc. ya NO bloquea la agenda.
ESTADOS_ACTIVOS = frozenset({EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA})


# ──────────────────────────────────────────────────────────────────────────────
# ENTIDAD PRINCIPAL: Cita
# ──────────────────────────────────────────────────────────────────────────────

# @dataclass genera automáticamente el constructor __init__ con todos los campos.
# Esto aplica el principio de encapsulamiento (enunciado sección 2: OOP).
@dataclass
class Cita:
    """
    Representa una cita médica y su ciclo de vida completo.

    Requisito enunciado 3.1.1:
        Crear · Confirmar · Cancelar · Reagendar · Validar disponibilidad ·
        Evitar conflictos · Gestionar estados.
    """

    # ── Atributos obligatorios ────────────────────────────────────────────────
    # Todos estos deben entregarse al crear la cita (sin valor por defecto).

    id: UUID            # Código único irrepetible que identifica esta cita.
    paciente_id: UUID   # ID del paciente que tiene la cita.
    medico_id: UUID     # ID del médico que atenderá la cita.
    especialidad: str   # Nombre de la especialidad, ej. "Cardiología".
    inicio: datetime    # Fecha y hora en que empieza la cita.
    fin: datetime       # Fecha y hora en que termina la cita.
    estado: EstadoCita  # Estado actual: PENDIENTE, CONFIRMADA, CANCELADA, etc.
    motivo: str         # Razón de la consulta, ej. "Control anual de presión".
    creada_en: datetime # Momento en que se registró la cita en el sistema.

    # ── Atributos opcionales ──────────────────────────────────────────────────
    # Tienen valor por defecto (None), así no es obligatorio entregarlos.

    # Anotaciones adicionales del médico o recepcionista sobre esta cita.
    notas: Optional[str] = field(default=None)

    # Si esta cita reemplaza a una anterior, guardamos el ID de esa cita original.
    # Permite tener trazabilidad del historial de reagendamientos.
    reagendada_desde_id: Optional[UUID] = field(default=None)

    # Si esta cita fue reemplazada por una nueva, guardamos el ID de la nueva.
    reagendada_hacia_id: Optional[UUID] = field(default=None)


    # ──────────────────────────────────────────────────────────────────────────
    # FACTORY METHOD: Cita.crear()
    # En lugar de construir la cita directamente con Cita(...), usamos este
    # método para VALIDAR todo antes de crear el objeto.
    # Es un @classmethod porque pertenece a la clase, no a una instancia.
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def crear(
        cls,                              # 'cls' es la clase Cita (no una instancia).
        paciente_id: UUID,                # Quién pide la cita.
        medico_id: UUID,                  # Quién la atenderá.
        especialidad: str,                # Especialidad requerida.
        inicio: datetime,                 # Cuándo empieza.
        duracion_minutos: int = 30,       # Duración en minutos (30 por defecto).
        motivo: str = "",                 # Razón de la consulta.
        ahora: Optional[datetime] = None, # Hora de referencia (útil para tests).
    ) -> Cita:
        """
        Crea y valida una nueva cita médica en estado PENDIENTE.

        Validaciones aplicadas (enunciado 3.1.1):
        - La duración debe ser un número positivo.
        - El inicio de la cita debe ser en el futuro (no en el pasado).
        """

        # Validación 1: la duración no puede ser 0 ni negativa.
        if duracion_minutos <= 0:
            raise ValueError(
                f"La duración debe ser positiva. Se recibió: {duracion_minutos} minutos."
            )

        # Determinamos el "ahora" de referencia para comparar con el inicio.
        # Si no se entregó ninguno (caso normal en producción), usamos el reloj del sistema.
        # 'tz=inicio.tzinfo' asegura que ambas horas tengan la misma zona horaria.
        referencia = ahora if ahora is not None else datetime.now(tz=inicio.tzinfo)

        # Validación 2: no se puede agendar una cita en el pasado.
        # Enunciado 3.1.1: "validar disponibilidad horaria".
        if inicio <= referencia:
            raise CitaEnPasadoError(
                f"No se puede agendar una cita en el pasado. "
                f"Inicio solicitado: {inicio.isoformat()}"
            )

        # Si todo es válido, construimos y devolvemos el objeto Cita.
        return cls(
            id=uuid4(),                # Generamos un ID único al azar.
            paciente_id=paciente_id,
            medico_id=medico_id,
            especialidad=especialidad,
            inicio=inicio,
            fin=inicio + timedelta(minutes=duracion_minutos),  # Calculamos el fin.
            estado=EstadoCita.PENDIENTE,  # Toda cita nueva empieza en PENDIENTE.
            motivo=motivo,
            creada_en=referencia,      # Registramos cuándo se creó.
        )


    # ──────────────────────────────────────────────────────────────────────────
    # TRANSICIONES DE ESTADO
    # Métodos públicos que implementan los flujos del enunciado (3.1.1):
    # confirmar, cancelar, reagendar. Todos usan _transicionar() internamente.
    # ──────────────────────────────────────────────────────────────────────────

    def confirmar(self) -> None:
        """Confirma la cita. Transición: PENDIENTE → CONFIRMADA."""
        self._transicionar(EstadoCita.CONFIRMADA)

    def cancelar(self) -> None:
        """Cancela la cita. Transición: PENDIENTE o CONFIRMADA → CANCELADA."""
        self._transicionar(EstadoCita.CANCELADA)

    def completar(self) -> None:
        """Marca la cita como realizada. Transición: CONFIRMADA → COMPLETADA."""
        self._transicionar(EstadoCita.COMPLETADA)

    def marcar_no_asistio(self) -> None:
        """Registra inasistencia del paciente. Transición: CONFIRMADA → NO_ASISTIO."""
        self._transicionar(EstadoCita.NO_ASISTIO)

    def reagendar(
        self,
        nueva_inicio: datetime,           # Nueva fecha y hora propuesta.
        duracion_minutos: int = 30,       # Duración de la nueva cita.
        ahora: Optional[datetime] = None, # Hora de referencia para la validación.
    ) -> Cita:
        """
        Reagenda la cita (enunciado 3.1.1: 'reagendar citas').

        Pasos:
        1. Marca esta cita como REAGENDADA (ya no ocupa la agenda).
        2. Crea una nueva cita con los mismos datos del paciente y médico.
        3. Registra el vínculo entre la cita original y la nueva (trazabilidad).

        Retorna la nueva cita creada para que el servicio la guarde en la BD.
        """
        # Paso 1: esta cita pasa a estado REAGENDADA.
        self._transicionar(EstadoCita.REAGENDADA)

        # Paso 2: creamos la nueva cita usando los mismos datos de origen.
        nueva = Cita.crear(
            paciente_id=self.paciente_id,
            medico_id=self.medico_id,
            especialidad=self.especialidad,
            inicio=nueva_inicio,
            duracion_minutos=duracion_minutos,
            motivo=self.motivo,
            ahora=ahora,
        )

        # Paso 3: enlazamos ambas citas para mantener el historial.
        nueva.reagendada_desde_id = self.id   # La nueva sabe de dónde viene.
        self.reagendada_hacia_id = nueva.id   # La original sabe hacia dónde fue.

        return nueva  # Devolvemos la nueva cita para que el servicio la persista.


    # ──────────────────────────────────────────────────────────────────────────
    # REGLAS DE NEGOCIO
    # Enunciado 3.1.1: "evitar conflictos de agenda" y "validar disponibilidad".
    # ──────────────────────────────────────────────────────────────────────────

    def se_solapa_con(self, otra: Cita) -> bool:
        """
        Devuelve True si esta cita se superpone en horario con otra cita del mismo médico.

        Condiciones para que haya solapamiento:
        1. Mismo médico (médicos distintos no comparten agenda).
        2. Ambas citas están activas (PENDIENTE o CONFIRMADA).
        3. Los intervalos de tiempo se superponen.
        """
        # Condición 1: si los médicos son distintos, no puede haber conflicto.
        if self.medico_id != otra.medico_id:
            return False

        # Condición 2: si alguna cita no está activa, no bloquea la agenda.
        if self.estado not in ESTADOS_ACTIVOS or otra.estado not in ESTADOS_ACTIVOS:
            return False

        # Condición 3: hay solapamiento si A empieza antes de que B termine,
        # Y B empieza antes de que A termine. Es el algoritmo estándar para
        # detectar superposición de intervalos de tiempo.
        return self.inicio < otra.fin and otra.inicio < self.fin

    def validar_no_solapa(self, citas_existentes: list[Cita]) -> None:
        """
        Revisa una lista de citas y lanza ConflictoDeAgenda si hay solapamiento.

        Se llama ANTES de registrar una cita nueva en la agenda para garantizar
        que no haya conflictos (enunciado 3.1.1: "evitar conflictos de agenda").
        """
        for existente in citas_existentes:
            # Nos saltamos la comparación de la cita consigo misma.
            if existente.id == self.id:
                continue

            # Si hay solapamiento con alguna cita existente, lanzamos el error.
            if self.se_solapa_con(existente):
                raise ConflictoDeAgenda(
                    f"Conflicto de agenda: el horario {self.inicio.isoformat()} – "
                    f"{self.fin.isoformat()} se superpone con la cita "
                    f"{existente.id} ({existente.inicio.isoformat()} – "
                    f"{existente.fin.isoformat()})."
                )


    # ──────────────────────────────────────────────────────────────────────────
    # PROPIEDADES CALCULADAS
    # @property convierte un método en un atributo de solo lectura.
    # Se recalculan cada vez que se piden, así nunca quedan desactualizadas.
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def duracion_minutos(self) -> int:
        """Cuántos minutos dura la cita (calculado a partir de fin - inicio)."""
        return int((self.fin - self.inicio).total_seconds() / 60)

    @property
    def esta_activa(self) -> bool:
        """True si la cita ocupa la agenda del médico (PENDIENTE o CONFIRMADA)."""
        return self.estado in ESTADOS_ACTIVOS


    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODO PRIVADO: _transicionar
    # Los métodos con _ al inicio son "privados por convención": solo deben
    # ser llamados desde dentro de esta misma clase, no desde afuera.
    # ──────────────────────────────────────────────────────────────────────────

    def _transicionar(self, nuevo_estado: EstadoCita) -> None:
        """
        Valida que el cambio de estado sea permitido y lo aplica.

        Consulta la tabla _TRANSICIONES para saber si desde el estado actual
        se puede pasar al nuevo estado. Si no está permitido, lanza un error.
        """
        # Obtenemos los estados permitidos desde el estado actual.
        # .get() devuelve frozenset() vacío si el estado no está en el diccionario.
        permitidos = _TRANSICIONES.get(self.estado, frozenset())

        # Si el nuevo estado no está entre los permitidos, lanzamos el error.
        if nuevo_estado not in permitidos:
            raise TransicionEstadoInvalida(
                f"No se puede cambiar el estado de "
                f"'{self.estado.value}' a '{nuevo_estado.value}'."
            )

        # Cambio válido: actualizamos el estado.
        self.estado = nuevo_estado


    # ──────────────────────────────────────────────────────────────────────────
    # REPRESENTACIÓN TEXTUAL
    # __repr__ define cómo se ve el objeto cuando lo imprimimos con print().
    # ──────────────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Representación legible de la cita para debugging y logs."""
        return (
            f"Cita("
            f"id={self.id}, "
            f"paciente={self.paciente_id}, "
            f"medico={self.medico_id}, "
            f"inicio={self.inicio.isoformat()}, "
            f"fin={self.fin.isoformat()}, "
            f"estado={self.estado.value}"
            f")"
        )
