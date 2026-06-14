"""Especialidades médicas disponibles en el sistema."""


class Especialidad:

    def __init__(self, nombre: str, descripcion: str = ""):
        self.nombre = nombre
        self.descripcion = descripcion

    def __repr__(self) -> str:
        return f"Especialidad({self.nombre!r})"


Especialidad.MEDICINA_GENERAL    = Especialidad("Medicina General",     "Atención primaria y diagnóstico general")
Especialidad.CARDIOLOGIA         = Especialidad("Cardiología",          "Enfermedades del corazón y sistema cardiovascular")
Especialidad.NEUROLOGIA          = Especialidad("Neurología",           "Sistema nervioso central y periférico")
Especialidad.TRAUMATOLOGIA       = Especialidad("Traumatología",        "Lesiones y enfermedades del sistema musculoesquelético")
Especialidad.PEDIATRIA           = Especialidad("Pediatría",            "Salud infantil desde el nacimiento hasta la adolescencia")
Especialidad.GINECOLOGIA         = Especialidad("Ginecología",          "Salud del sistema reproductor femenino")
Especialidad.OFTALMOLOGIA        = Especialidad("Oftalmología",         "Enfermedades y cirugías del ojo")
Especialidad.DERMATOLOGIA        = Especialidad("Dermatología",         "Enfermedades de la piel, cabello y uñas")
Especialidad.PSIQUIATRIA         = Especialidad("Psiquiatría",          "Salud mental y trastornos psiquiátricos")
Especialidad.UROLOGIA            = Especialidad("Urología",             "Sistema urinario y reproductor masculino")
Especialidad.GASTROENTEROLOGIA   = Especialidad("Gastroenterología",    "Enfermedades del aparato digestivo")
Especialidad.OTORRINOLARINGOLOGIA = Especialidad("Otorrinolaringología", "Oído, nariz y garganta")
