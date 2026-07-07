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


# Ciclo de vida de una oferta de cupo liberado en la lista de espera:
# el sistema la crea (PENDIENTE) cuando se libera una hora; el paciente la acepta
# (ACEPTADA) y se crea su cita, o la rechaza (RECHAZADA) para seguir esperando o
# salir de la lista.
class EstadoOferta(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA  = "aceptada"
    RECHAZADA = "rechazada"
