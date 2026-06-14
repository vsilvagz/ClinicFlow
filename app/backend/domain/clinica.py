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
    def __init__(self, nombre: str, direccion: str):
        self.nombre = nombre      # Nombre de la clínica, ej: "Clínica Las Condes".
        self.direccion = direccion  # Dirección física de la clínica, ej: "Av. Vitacura 5951".
        self.medicos_disponibles: list[Medico] = []          # Lista de médicos que atienden en esta clínica.
        self.especialidades_presentes: list[Especialidad] = []  # Lista de especialidades disponibles en esta clínica.
