"""Entidad Clínica: agrupa médicos y especialidades de un centro médico."""

from app.backend.domain.especialidades import Especialidad
from app.backend.domain.usuarios import Medico


class Clinica:
    """Representa un centro médico. Puede haber varias instancias (sucursales)."""

    def __init__(self, RUT_empresa, nombre: str, direccion: str = "Dirección no especificada"):
        self.RUT_empresa = RUT_empresa
        self.nombre = nombre
        self.direccion = direccion
        self.medicos_disponibles: list[Medico] = []
        self.especialidades_presentes: list[Especialidad] = []

    def registrar_medico(self, medico: Medico) -> None:
        if medico not in self.medicos_disponibles:
            self.medicos_disponibles.append(medico)

    def registrar_especialidad(self, especialidad: Especialidad) -> None:
        if especialidad not in self.especialidades_presentes:
            self.especialidades_presentes.append(especialidad)
