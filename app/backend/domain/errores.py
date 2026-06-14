"""Excepciones del dominio."""


class ClinicFlowError(Exception):
    """Base para todos los errores de dominio."""


class TransicionEstadoInvalida(ClinicFlowError):
    """Transición de estado no permitida para la cita."""


class CitaEnPasadoError(ClinicFlowError):
    """Intento de agendar una cita en una fecha/hora ya pasada."""


class ConflictoDeAgenda(ClinicFlowError):
    """El horario solicitado se solapa con una cita existente del médico."""


class HorarioNoDisponible(ClinicFlowError):
    """El bloque horario solicitado está fuera de la agenda del médico."""


class AgendaSuspendida(ClinicFlowError):
    """La agenda del médico está suspendida en el período solicitado."""


class CitaNoEncontrada(ClinicFlowError):
    """No se encontró la cita solicitada."""


class PacienteNoEncontrado(ClinicFlowError):
    """No se encontró el paciente solicitado."""


class MedicoNoEncontrado(ClinicFlowError):
    """No se encontró el médico solicitado."""


class PermisoDenegado(ClinicFlowError):
    """El usuario no tiene permisos para realizar esta operación."""


class ListaEsperaLlena(ClinicFlowError):
    """La lista de espera de la especialidad está al máximo de capacidad."""


class PacienteYaEnEspera(ClinicFlowError):
    """El paciente ya está inscrito en la lista de espera de esa especialidad."""


class DerivacionNoEncontrada(ClinicFlowError):
    """No se encontró la derivación solicitada."""


class DerivacionExpirada(ClinicFlowError):
    """La derivación ya no es válida por haber superado su plazo de vigencia."""


class DerivacionYaUsada(ClinicFlowError):
    """La derivación ya fue completada o rechazada y no puede utilizarse nuevamente."""
