"""Tipos de usuario del sistema y sus permisos."""


class Usuario:
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        self.RUN_usuario = RUN_usuario
        self.nombre = nombre
        self.correo = correo
        self.telefono = telefono


class Paciente(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self.derivaciones_especialidades_permitidas: list[str] = []


class Medico(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, especialidad):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self.especialidad = especialidad


class Recepcionista(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, clinica):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self.clinica = clinica


class Administrador(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self.acceso_vip = True
