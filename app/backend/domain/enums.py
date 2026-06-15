"""Enumeraciones del dominio: roles, estados y prioridades."""

from enum import Enum


class EstadoCita(str, Enum):
    PENDIENTE  = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA  = "cancelada"
    REAGENDADA = "reagendada"
    COMPLETADA = "completada"
    NO_ASISTIO = "no_asistio"


class RolUsuario(str, Enum):
    ADMINISTRADOR = "administrador"
    RECEPCIONISTA = "recepcionista"
    MEDICO        = "medico"
    PACIENTE      = "paciente"


class PrioridadEspera(str, Enum):
    BAJA    = "baja"
    NORMAL  = "normal"
    ALTA    = "alta"
    URGENTE = "urgente"


# Ciclo de vida de una derivación:
# el médico la emite (PENDIENTE), el paciente agenda la cita (COMPLETADA),
# o el plazo vence sin que lo haga (EXPIRADA).
class EstadoDerivacion(str, Enum):
    PENDIENTE  = "pendiente"
    COMPLETADA = "completada"
    EXPIRADA   = "expirada"
