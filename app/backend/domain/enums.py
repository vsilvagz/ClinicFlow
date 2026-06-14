"""Enumeraciones del dominio: roles, estados y prioridades."""

# 'enum' es un módulo de Python que nos permite crear listas de valores fijos con nombre.
# Así evitamos escribir texto libre como "pendiente" y cometer errores de tipeo.
from enum import Enum


# EstadoCita define todos los estados posibles de una cita médica.
# Hereda de str y de Enum: esto permite que el valor sea texto Y nombre al mismo tiempo.
class EstadoCita(str, Enum):
    PENDIENTE  = "pendiente"   # La cita fue creada pero aún no confirmada por nadie.
    CONFIRMADA = "confirmada"  # Un recepcionista o el médico confirmó la cita.
    CANCELADA  = "cancelada"   # La cita fue anulada (paciente o clínica la canceló).
    REAGENDADA = "reagendada"  # Se cambió la hora; esta cita fue reemplazada por una nueva.
    COMPLETADA = "completada"  # La consulta médica se realizó con éxito.
    NO_ASISTIO = "no_asistio"  # El paciente no se presentó a la cita.


# RolUsuario define los cuatro tipos de usuario que existen en el sistema.
# Cada rol tiene permisos distintos (ver usuarios.py para más detalle).
class RolUsuario(str, Enum):
    ADMINISTRADOR = "administrador"  # Acceso completo al sistema.
    RECEPCIONISTA = "recepcionista"  # Gestiona citas y listas de espera.
    MEDICO        = "medico"         # Ve y gestiona su propia agenda.
    PACIENTE      = "paciente"       # Puede pedir, cancelar y reagendar sus citas.


# PrioridadEspera define el nivel de urgencia de un paciente en la lista de espera.
# Sirve para atender primero a quienes más lo necesitan.
class PrioridadEspera(str, Enum):
    BAJA    = "baja"    # No hay apuro, puede esperar bastante tiempo.
    NORMAL  = "normal"  # Prioridad estándar para la mayoría de los casos.
    ALTA    = "alta"    # El paciente necesita atención pronto.
    URGENTE = "urgente" # El paciente necesita atención lo antes posible.


# EstadoDerivacion define el ciclo de vida de una derivación médica.
# Una derivación es cuando un médico envía al paciente a ver a otro especialista.
class EstadoDerivacion(str, Enum):
    PENDIENTE  = "pendiente"   # El médico emitió la derivación; el paciente aún no la acepta.
    ACEPTADA   = "aceptada"    # El paciente aceptó y ya puede agendar en la especialidad destino.
    RECHAZADA  = "rechazada"   # El paciente rechazó la derivación; ya no es válida.
    COMPLETADA = "completada"  # El paciente agendó y asistió a la cita derivada.
    EXPIRADA   = "expirada"    # El plazo de la derivación venció sin que el paciente actuara.
