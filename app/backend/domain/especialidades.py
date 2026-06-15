"""Especialidades médicas disponibles en el sistema."""


# Clase Especialidad: representa una especialidad médica como Cardiología o Pediatría.
# No hereda de nada especial; es una clase simple que guarda nombre y descripción.
class Especialidad:

    # __init__ es el constructor: se ejecuta automáticamente al crear un objeto Especialidad.
    # 'nombre' es obligatorio; 'descripcion' es opcional (tiene valor por defecto vacío).
    def __init__(self, nombre: str, descripcion: str = ""):
        self.nombre = nombre           # Nombre de la especialidad, ej: "Cardiología".
        self.descripcion = descripcion # Descripción breve de qué trata la especialidad.

    # __eq__ define cuándo dos especialidades se consideran "iguales".
    # Las comparamos por nombre: dos Especialidad("Cardiología") son la misma,
    # aunque sean objetos distintos en memoria. Esto evita duplicados al usar
    # "especialidad not in lista" (ver Clinica.registrar_especialidad).
    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Especialidad):
            return NotImplemented
        return self.nombre == otro.nombre

    # __hash__ debe ser coherente con __eq__: si dos objetos son iguales,
    # deben tener el mismo hash. Lo derivamos del nombre para poder usar
    # Especialidad en sets y como clave de diccionarios.
    def __hash__(self) -> int:
        return hash(self.nombre)

    # __repr__ define cómo se ve el objeto al imprimirlo con print().
    # Útil para depuración (ver qué especialidad es en los logs).
    def __repr__(self) -> str:
        return f"Especialidad({self.nombre!r})"  # Ej: Especialidad('Cardiología')


# A continuación creamos instancias predefinidas de las especialidades más comunes.
# Las guardamos como atributos de la propia clase para que sean fáciles de usar:
# en lugar de escribir Especialidad("Cardiología", "..."), se puede escribir
# Especialidad.CARDIOLOGIA desde cualquier parte del código.

# Especialidad.MEDICINA_GENERAL     = Especialidad("Medicina General",      "Atención primaria y diagnóstico general")
# Especialidad.CARDIOLOGIA          = Especialidad("Cardiología",           "Enfermedades del corazón y sistema cardiovascular")
# Especialidad.NEUROLOGIA           = Especialidad("Neurología",            "Sistema nervioso central y periférico")
# Especialidad.TRAUMATOLOGIA        = Especialidad("Traumatología",         "Lesiones y enfermedades del sistema musculoesquelético")
# Especialidad.PEDIATRIA            = Especialidad("Pediatría",             "Salud infantil desde el nacimiento hasta la adolescencia")
# Especialidad.GINECOLOGIA          = Especialidad("Ginecología",           "Salud del sistema reproductor femenino")
# Especialidad.OFTALMOLOGIA         = Especialidad("Oftalmología",          "Enfermedades y cirugías del ojo")
# Especialidad.DERMATOLOGIA         = Especialidad("Dermatología",          "Enfermedades de la piel, cabello y uñas")
# Especialidad.PSIQUIATRIA          = Especialidad("Psiquiatría",           "Salud mental y trastornos psiquiátricos")
# Especialidad.UROLOGIA             = Especialidad("Urología",              "Sistema urinario y reproductor masculino")
# Especialidad.GASTROENTEROLOGIA    = Especialidad("Gastroenterología",     "Enfermedades del aparato digestivo")
# Especialidad.OTORRINOLARINGOLOGIA = Especialidad("Otorrinolaringología",  "Oído, nariz y garganta")

