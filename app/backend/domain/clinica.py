"""Entidad Clínica: agrupa médicos y especialidades de un centro médico."""

# Importamos Especialidad para guardar las especialidades que ofrece la clínica.
from app.backend.domain.especialidades import Especialidad

# Importamos Medico para guardar los médicos que trabajan en la clínica.
from app.backend.domain.usuarios import Medico


# Clinica representa un centro médico del sistema.
# Una clínica agrupa a sus médicos y las especialidades que ofrece.
# Puede haber varias clínicas usando el sistema (ej: distintas sucursales).
class Clinica:

    # __init__ es el constructor: se ejecuta al crear un objeto Clinica.
    def __init__(self, RUT_empresa, nombre: str, direccion: str = "Dirección no especificada"):
        self.RUT_empresa = RUT_empresa
        self.nombre = nombre 
        self.direccion = direccion 
        self.medicos_disponibles: list[Medico] = [] 
        self.especialidades_presentes: list[Especialidad] = [] 

    def registrar_medico(self, medico: Medico) -> None:
        """Agrega un nuevo médico al staff de la clínica si no está repetido."""
        if medico not in self.medicos_disponibles:
            self.medicos_disponibles.append(medico)
            print(f"Médico {medico.nombre} registrado en {self.nombre}.")

    def registrar_especialidad(self, especialidad: Especialidad) -> None:
        """Agrega una especialidad a los servicios de la clínica si no existe."""
        if especialidad not in self.especialidades_presentes:
            self.especialidades_presentes.append(especialidad)
            print(f"Especialidad {especialidad.nombre} habilitada en {self.nombre}.")