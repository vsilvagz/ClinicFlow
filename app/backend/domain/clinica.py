"""Entidad Clínica: agrupa médicos y especialidades de un centro médico."""

from app.backend.domain.especialidades import Especialidad
from app.backend.domain.usuarios import Medico


class Clinica:

    def __init__(self, nombre: str, direccion: str):
        self.nombre = nombre
        self.direccion = direccion
        self.medicos_disponibles: list[Medico] = []
        self.especialidades_presentes: list[Especialidad] = []
