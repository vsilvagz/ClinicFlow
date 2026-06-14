"""Enumeraciones del dominio: roles, estados y prioridades."""

from enum import Enum


class EstadoCita(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    REAGENDADA = "reagendada"
    COMPLETADA = "completada"
    NO_ASISTIO = "no_asistio"


class RolUsuario(str, Enum):
    ADMINISTRADOR = "administrador"
    RECEPCIONISTA = "recepcionista"
    MEDICO = "medico"
    PACIENTE = "paciente"


class PrioridadEspera(str, Enum):
    BAJA = "baja"
    NORMAL = "normal"
    ALTA = "alta"
    URGENTE = "urgente"


class EstadoDerivacion(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    COMPLETADA = "completada"
    EXPIRADA = "expirada"
