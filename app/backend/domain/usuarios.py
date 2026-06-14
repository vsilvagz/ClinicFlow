"""Tipos de usuario del sistema y sus permisos."""

from agenda import Agenda
from especialidades import Especialidad


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


# Paciente solo puede hacer cosas relacionadas con sus propias citas, además de interactuar con Telegram.
class Paciente(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._derivaciones_especialidades_permitidas: list[str] = []
        # Si un médico activó una derivación, esta queda validada dentro de la lista para que el sistema pueda aprobar una hora en dicha especialidad.

    @property
    def derivaciones_especialidades_permitidas(self) -> list[str]:
        return list(self._derivaciones_especialidades_permitidas)

    def agregar_derivacion(self, especialidad: str):
        self._derivaciones_especialidades_permitidas.append(especialidad)


# Médico solo puede hacer cosas relacionadas con su propia agenda agenda, además de ver info de sus pacientes y derivaciones.
class Medico(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, especialidad: Especialidad):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._especialidad = especialidad
        self._agenda: Agenda = Agenda()

    @property
    def especialidad(self) -> Especialidad:
        return self._especialidad

    @especialidad.setter
    def especialidad(self, valor: Especialidad):
        self._especialidad = valor

    @property
    def agenda(self) -> Agenda:
        return self._agenda


# Recepcionista puede hacer cosas relacionadas con las agendas de los médicos de su clínica y las citas de los pacientes. 
# Pueden gestionar citas, reagendar pacientes, administrar listas de espera y visualizar agendas clínicas.
class Recepcionista(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, clinica):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._clinica = clinica
        # El/La recepcionista trabaja en una clínica específica (Enunciado especifica "Administrar clínicas").
        # Útil si por ejemplo hay distintas sucursales.

    @property
    def clinica(self):
        return self._clinica

    @clinica.setter
    def clinica(self, valor):
        self._clinica = valor

# Administrador(a) tiene acceso completo al sistema.
class Administrador(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self.__acceso_vip = True
        # Acceso total para administrar, configurar y visualiar todo el sistema.
        # ESTA ÚLTIMA VARIABLE SERÁ ÚTIL EN EL FUTURO PARA DARLE AL RECEPCIONSITA LOS PERMISOS CORRESPONDIENTES.

    @property
    def acceso_vip(self) -> bool:
        return self.__acceso_vip
