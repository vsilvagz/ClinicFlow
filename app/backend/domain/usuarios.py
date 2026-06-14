"""Tipos de usuario del sistema y sus permisos."""


class Usuario:
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        self.__RUN_usuario = RUN_usuario
        self._nombre = nombre
        self._correo = correo
        self._telefono = telefono

    @property
    def RUN_usuario(self) -> int:
        return self.__RUN_usuario

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str):
        self._nombre = valor

    @property
    def correo(self) -> str:
        return self._correo

    @correo.setter
    def correo(self, valor: str):
        if "@" not in valor:
            raise ValueError("El correo no es válido.")
        self._correo = valor

    @property
    def telefono(self) -> int:
        return self._telefono

    @telefono.setter
    def telefono(self, valor: int):
        self._telefono = valor


class Paciente(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._derivaciones_especialidades_permitidas: list[str] = []

    @property
    def derivaciones_especialidades_permitidas(self) -> list[str]:
        return list(self._derivaciones_especialidades_permitidas)

    def agregar_derivacion(self, especialidad: str):
        self._derivaciones_especialidades_permitidas.append(especialidad)


class Medico(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, especialidad):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._especialidad = especialidad

    @property
    def especialidad(self):
        return self._especialidad

    @especialidad.setter
    def especialidad(self, valor):
        self._especialidad = valor


class Recepcionista(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, clinica):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._clinica = clinica

    @property
    def clinica(self):
        return self._clinica

    @clinica.setter
    def clinica(self, valor):
        self._clinica = valor


class Administrador(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self.__acceso_vip = True

    @property
    def acceso_vip(self) -> bool:
        return self.__acceso_vip
