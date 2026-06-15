"""Especialidades médicas disponibles en el sistema."""


class Especialidad:

    def __init__(self, nombre: str, descripcion: str = ""):
        self.nombre = nombre
        self.descripcion = descripcion

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Especialidad):
            return NotImplemented
        return self.nombre == otro.nombre

    def __hash__(self) -> int:
        return hash(self.nombre)

    def __repr__(self) -> str:
        return f"Especialidad({self.nombre!r})"
