"""Excepciones del dominio."""

# En Python, cuando algo sale mal lanzamos una "excepción" (error controlado).
# Aquí definimos nuestros propios tipos de error para que el sistema pueda
# diferenciar exactamente qué problema ocurrió.


# ClinicFlowError es la clase base de todos los errores del sistema.
# Hereda de Exception, que es el tipo base de todos los errores en Python.
# Tener una clase base propia nos permite atrapar "cualquier error de ClinicFlow"
# con una sola instrucción en el código.
class ClinicFlowError(Exception):
    """Base para todos los errores de dominio."""


# Se lanza cuando se intenta cambiar el estado de una cita o derivación
# de una forma que no está permitida. Ej: confirmar una cita ya cancelada.
class TransicionEstadoInvalida(ClinicFlowError):
    """Transición de estado no permitida para la cita."""


# Se lanza cuando alguien intenta crear una cita en una hora que ya pasó.
# Ej: pedir hora para ayer.
class CitaEnPasadoError(ClinicFlowError):
    """Intento de agendar una cita en una fecha/hora ya pasada."""


# Se lanza cuando dos citas del mismo médico se superponen en horario.
# Ej: el médico ya tiene una cita de 10:00 a 10:30 y se intenta agregar otra a las 10:15.
class ConflictoDeAgenda(ClinicFlowError):
    """El horario solicitado se solapa con una cita existente del médico."""


# Se lanza cuando se intenta agendar fuera del horario de atención del médico.
# Ej: agendar a las 22:00 si el médico solo atiende de 09:00 a 17:00.
class HorarioNoDisponible(ClinicFlowError):
    """El bloque horario solicitado está fuera de la agenda del médico."""


# Se lanza cuando el médico tiene su agenda suspendida (ej: vacaciones o paro)
# y alguien intenta agendar en ese período.
class AgendaSuspendida(ClinicFlowError):
    """La agenda del médico está suspendida en el período solicitado."""


# Se lanza cuando se busca una cita por su ID y no existe en el sistema.
class CitaNoEncontrada(ClinicFlowError):
    """No se encontró la cita solicitada."""


# Se lanza cuando se busca un paciente por su RUN y no existe en el sistema.
class PacienteNoEncontrado(ClinicFlowError):
    """No se encontró el paciente solicitado."""


# Se lanza cuando se busca un médico por su RUN y no existe en el sistema.
class MedicoNoEncontrado(ClinicFlowError):
    """No se encontró el médico solicitado."""


# Se lanza cuando un usuario intenta hacer algo que su rol no permite.
# Ej: un paciente intenta ver la agenda de otro paciente.
class PermisoDenegado(ClinicFlowError):
    """El usuario no tiene permisos para realizar esta operación."""


# Se lanza cuando la lista de espera ya llegó a su capacidad máxima.
class ListaEsperaLlena(ClinicFlowError):
    """La lista de espera de la especialidad está al máximo de capacidad."""


# Se lanza cuando un paciente intenta inscribirse en una lista de espera
# en la que ya estaba inscrito.
class PacienteYaEnEspera(ClinicFlowError):
    """El paciente ya está inscrito en la lista de espera de esa especialidad."""


# Se lanza cuando se busca una derivación por su ID y no existe en el sistema.
class DerivacionNoEncontrada(ClinicFlowError):
    """No se encontró la derivación solicitada."""


# Se lanza cuando se intenta usar una derivación cuyo plazo de vigencia ya venció.
class DerivacionExpirada(ClinicFlowError):
    """La derivación ya no es válida por haber superado su plazo de vigencia."""


# Se lanza cuando se intenta usar una derivación que ya fue completada o rechazada.
class DerivacionYaUsada(ClinicFlowError):
    """La derivación ya fue completada o rechazada y no puede utilizarse nuevamente."""
