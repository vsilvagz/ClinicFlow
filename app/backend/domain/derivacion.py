"""Derivación de pacientes entre especialidades o profesionales."""

# Permite usar el nombre 'Derivacion' dentro de la propia clase sin errores.
from __future__ import annotations

# dataclass: genera __init__ automáticamente; field: configura valores por defecto.
from dataclasses import dataclass, field

# datetime: fecha y hora, ej: 2026-06-14 10:30.
# timedelta: duración, ej: 30 días.
from datetime import datetime, timedelta

# Optional[T]: indica que el valor puede ser de tipo T o None (vacío).
from typing import Optional

# UUID: código único irrepetible para identificar cada derivación.
# uuid4: función que genera un UUID aleatorio.
from uuid import UUID, uuid4

# Importamos los estados posibles de una derivación desde enums.py.
from app.backend.domain.enums import EstadoDerivacion

# Importamos los errores que lanzaremos si algo sale mal.
from app.backend.domain.errores import DerivacionExpirada, TransicionEstadoInvalida


# ──────────────────────────────────────────────────────────────────────────────
# MÁQUINA DE ESTADOS DE LA DERIVACIÓN
# Define qué cambios de estado están permitidos.
# ──────────────────────────────────────────────────────────────────────────────

# Diccionario que mapea cada estado al conjunto de estados a los que puede pasar.
_TRANSICIONES: dict[EstadoDerivacion, frozenset[EstadoDerivacion]] = {
    # PENDIENTE: la derivación fue emitida por el médico, el paciente aún no actúa.
    EstadoDerivacion.PENDIENTE: frozenset({
        EstadoDerivacion.ACEPTADA,   # El paciente acepta ser derivado.
        EstadoDerivacion.RECHAZADA,  # El paciente rechaza la derivación.
        EstadoDerivacion.EXPIRADA,   # El plazo venció sin que el paciente actuara.
    }),
    # ACEPTADA: el paciente aceptó; puede agendar cita en la especialidad destino.
    EstadoDerivacion.ACEPTADA: frozenset({
        EstadoDerivacion.COMPLETADA, # El paciente agendó y asistió a la cita derivada.
        EstadoDerivacion.EXPIRADA,   # El plazo venció antes de que agendara.
    }),
    # Estados finales: una vez aquí, la derivación no puede cambiar.
    EstadoDerivacion.RECHAZADA:  frozenset(),  # El paciente rechazó; ya no se puede revertir.
    EstadoDerivacion.COMPLETADA: frozenset(),  # La derivación se completó con éxito.
    EstadoDerivacion.EXPIRADA:   frozenset(),  # El plazo venció; ya no es válida.
}

# Número de días de vigencia por defecto cuando no se especifica otro valor.
DIAS_VIGENCIA_DEFAULT = 30  # Una derivación dura 30 días por defecto.


# ──────────────────────────────────────────────────────────────────────────────
# ENTIDAD PRINCIPAL: Derivacion
# ──────────────────────────────────────────────────────────────────────────────

@dataclass  # genera __init__ automáticamente con todos los atributos declarados abajo
class Derivacion:
    """
    Representa una derivación médica hacia otra especialidad o profesional.

    Ciclo de vida:
        PENDIENTE → ACEPTADA → COMPLETADA
        PENDIENTE → RECHAZADA
        PENDIENTE | ACEPTADA → EXPIRADA
    """

    id: UUID              # Código único que identifica esta derivación (UUID propio).
    paciente_id: int      # RUN_usuario del paciente que está siendo derivado.
    medico_origen_id: int # RUN_usuario del médico que emitió la derivación.
    especialidad_destino: str  # Nombre de la especialidad a la que se deriva, ej: "Cardiología".
    motivo: str           # Razón clínica de la derivación, ej: "Control post-operatorio".
    estado: EstadoDerivacion   # Estado actual: PENDIENTE, ACEPTADA, RECHAZADA, etc.
    creada_en: datetime   # Fecha y hora en que el médico emitió la derivación.
    expira_en: datetime   # Fecha y hora límite; después de esta ya no es válida.

    # Atributos opcionales (pueden quedar en None si no aplican):
    medico_destino_id: Optional[int]  = field(default=None)  # RUN del médico destino específico (si se asignó uno).
    cita_resultante_id: Optional[UUID] = field(default=None) # UUID de la Cita que resultó de esta derivación.
    notas: Optional[str] = field(default=None)               # Observaciones clínicas adicionales del médico.

    # ── Factory method ─────────────────────────────────────────────────────────

    @classmethod  # pertenece a la clase, no a una instancia
    def crear(
        cls,
        paciente_id: int,                     # RUN del paciente a derivar.
        medico_origen_id: int,                # RUN del médico que emite la derivación.
        especialidad_destino: str,            # Especialidad de destino.
        motivo: str,                          # Motivo clínico.
        dias_vigencia: int = DIAS_VIGENCIA_DEFAULT,  # Días de validez (30 por defecto).
        medico_destino_id: Optional[int] = None,     # RUN del médico destino (opcional).
        notas: Optional[str] = None,          # Notas adicionales (opcional).
        ahora: Optional[datetime] = None,     # Hora de referencia (útil para tests).
    ) -> Derivacion:
        """Crea una nueva derivación en estado PENDIENTE."""

        # Validación 1: la vigencia debe ser un número positivo de días.
        if dias_vigencia <= 0:
            raise ValueError(
                f"La vigencia debe ser un número positivo de días, se recibió {dias_vigencia}."
            )

        # Validación 2: la especialidad destino no puede estar vacía.
        especialidad_destino = especialidad_destino.strip()  # Eliminamos espacios en blanco.
        if not especialidad_destino:  # Si quedó vacía después de limpiar...
            raise ValueError("La especialidad destino no puede estar vacía.")

        # Determinamos el "ahora" de referencia (para poder simular fechas en tests).
        referencia = ahora if ahora is not None else datetime.now()

        # Creamos y devolvemos el objeto Derivacion con todos los datos.
        return cls(
            id=uuid4(),                                         # Generamos un UUID único para esta derivación.
            paciente_id=paciente_id,
            medico_origen_id=medico_origen_id,
            especialidad_destino=especialidad_destino,
            motivo=motivo,
            estado=EstadoDerivacion.PENDIENTE,                  # Toda derivación nueva empieza en PENDIENTE.
            creada_en=referencia,                               # Registramos cuándo se creó.
            expira_en=referencia + timedelta(days=dias_vigencia), # Calculamos cuándo expira.
            medico_destino_id=medico_destino_id,
            notas=notas,
        )

    # ── Transiciones de estado ─────────────────────────────────────────────────

    def aceptar(self, ahora: Optional[datetime] = None) -> None:
        """El paciente acepta la derivación: PENDIENTE → ACEPTADA."""
        self._verificar_vigencia(ahora)              # Primero verificamos que no haya vencido.
        self._transicionar(EstadoDerivacion.ACEPTADA) # Luego cambiamos el estado.

    def rechazar(self) -> None:
        """El paciente rechaza la derivación: PENDIENTE → RECHAZADA."""
        self._transicionar(EstadoDerivacion.RECHAZADA)  # Cambiamos el estado a RECHAZADA.

    def completar(self, cita_id: UUID) -> None:
        """El paciente agendó gracias a esta derivación: ACEPTADA → COMPLETADA."""
        self._transicionar(EstadoDerivacion.COMPLETADA)  # Cambiamos el estado a COMPLETADA.
        self.cita_resultante_id = cita_id  # Guardamos el UUID de la cita que resultó.

    def expirar(self) -> None:
        """El plazo venció sin que el paciente actuara: PENDIENTE|ACEPTADA → EXPIRADA."""
        self._transicionar(EstadoDerivacion.EXPIRADA)  # Cambiamos el estado a EXPIRADA.

    # ── Reglas de negocio ──────────────────────────────────────────────────────

    def esta_vigente(self, ahora: Optional[datetime] = None) -> bool:
        """Devuelve True si la derivación aún está activa y no ha vencido."""
        referencia = ahora if ahora is not None else datetime.now()  # Hora de referencia.
        activos = {EstadoDerivacion.PENDIENTE, EstadoDerivacion.ACEPTADA}  # Estados considerados activos.
        return self.estado in activos and referencia < self.expira_en  # Activa Y dentro del plazo.

    def puede_agendar(self, ahora: Optional[datetime] = None) -> bool:
        """Devuelve True si el paciente puede usar esta derivación para agendar una cita."""
        # Solo se puede agendar si la derivación fue ACEPTADA Y sigue vigente.
        return self.estado == EstadoDerivacion.ACEPTADA and self.esta_vigente(ahora)

    def verificar_y_expirar_si_corresponde(self, ahora: Optional[datetime] = None) -> bool:
        """
        Revisa si la derivación venció y la expira automáticamente si corresponde.
        Devuelve True si se expiró ahora, False si ya estaba expirada o sigue vigente.
        """
        referencia = ahora if ahora is not None else datetime.now()  # Hora de referencia.
        activos = {EstadoDerivacion.PENDIENTE, EstadoDerivacion.ACEPTADA}  # Solo expiramos estados activos.
        if self.estado in activos and referencia >= self.expira_en:  # Si venció...
            self.expirar()   # ...la marcamos como EXPIRADA.
            return True      # Avisamos que sí se expiró en esta llamada.
        return False         # No se expiró (ya estaba expirada o sigue vigente).

    # ── Propiedades calculadas ─────────────────────────────────────────────────

    @property  # convierte este método en atributo de solo lectura
    def dias_restantes(self) -> int:
        """Días que restan hasta el vencimiento (negativo si ya expiró)."""
        delta = self.expira_en - datetime.now()  # Diferencia entre la expiración y ahora.
        return delta.days  # Extraemos solo los días de esa diferencia.

    @property
    def esta_activa(self) -> bool:
        """Devuelve True si la derivación puede seguir progresando (no es estado final)."""
        return self.estado in {EstadoDerivacion.PENDIENTE, EstadoDerivacion.ACEPTADA}

    # ── Métodos privados ───────────────────────────────────────────────────────

    def _verificar_vigencia(self, ahora: Optional[datetime] = None) -> None:
        """Lanza DerivacionExpirada si el plazo ya venció."""
        referencia = ahora if ahora is not None else datetime.now()  # Hora de referencia.
        if referencia >= self.expira_en:  # Si el tiempo de referencia superó la fecha de expiración...
            raise DerivacionExpirada(     # ...lanzamos el error.
                f"La derivación {self.id} expiró el {self.expira_en.isoformat()}."
            )

    def _transicionar(self, nuevo_estado: EstadoDerivacion) -> None:
        """Valida y ejecuta el cambio de estado consultando _TRANSICIONES."""
        permitidos = _TRANSICIONES.get(self.estado, frozenset())  # Obtenemos los estados permitidos.
        if nuevo_estado not in permitidos:  # Si el nuevo estado no está permitido...
            raise TransicionEstadoInvalida(  # ...lanzamos el error.
                f"No se puede pasar de '{self.estado.value}' a '{nuevo_estado.value}'"
            )
        self.estado = nuevo_estado  # Si está permitido, actualizamos el estado.

    def __repr__(self) -> str:
        """Representación legible de la derivación para debugging."""
        return (
            f"Derivacion(id={self.id}, paciente={self.paciente_id}, "
            f"especialidad='{self.especialidad_destino}', estado={self.estado.value}, "
            f"expira={self.expira_en.isoformat()})"
        )
