"""Tipos de usuario del sistema y sus permisos."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from app.backend.domain.agenda import Agenda, Bloqueo, Suspension
from app.backend.domain.citas import Cita
from app.backend.domain.derivacion import Derivacion
from app.backend.domain.especialidades import Especialidad

if TYPE_CHECKING:
    from app.backend.domain.lista_espera import Lista_de_Espera


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
        self._citas: list[Cita] = []

    @property
    def derivaciones_especialidades_permitidas(self) -> list[str]:
        return list(self._derivaciones_especialidades_permitidas)

    def agregar_derivacion(self, especialidad: str) -> None:
        self._derivaciones_especialidades_permitidas.append(especialidad)

    def registrar_cita(self, cita: Cita) -> None:
        self._citas.append(cita)

    def citas_activas(self) -> list[Cita]:
        return [c for c in self._citas if c.esta_activa]

    def tiene_cita_en_especialidad(self, especialidad: str) -> bool:
        return any(c.especialidad == especialidad for c in self.citas_activas())

    def historial_citas(self) -> list[Cita]:
        return list(self._citas)


# Médico solo puede hacer cosas relacionadas con su propia agenda agenda, además de ver info de sus pacientes y derivaciones.
class Medico(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, especialidad: Especialidad):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._especialidad = especialidad
        self._agenda: Agenda = Agenda()
        self._derivaciones_emitidas: list[Derivacion] = []

    @property
    def especialidad(self) -> Especialidad:
        return self._especialidad

    @especialidad.setter
    def especialidad(self, valor: Especialidad):
        self._especialidad = valor

    @property
    def agenda(self) -> Agenda:
        return self._agenda

    def bloquear_horario(self, inicio: datetime, fin: datetime, motivo: str = "") -> Bloqueo:
        return self._agenda.bloquear(inicio, fin, motivo)

    def suspender_agenda(self, inicio: datetime, fin: datetime, motivo: str = "") -> tuple[Suspension, list[Cita]]:
        return self._agenda.suspender(inicio, fin, motivo)

    def registrar_derivacion(self, derivacion: Derivacion) -> None:
        self._derivaciones_emitidas.append(derivacion)

    def derivaciones_vigentes(self) -> list[Derivacion]:
        return [d for d in self._derivaciones_emitidas if d.esta_activa]

    def historial_derivaciones(self) -> list[Derivacion]:
        return list(self._derivaciones_emitidas)


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

    # ── Gestión de citas ──────────────────────────────────────────────────────

    def confirmar_cita(self, cita: Cita) -> None:
        cita.confirmar()

    def cancelar_cita(self, cita: Cita) -> None:
        cita.cancelar()

    def marcar_no_asistio(self, cita: Cita) -> None:
        cita.marcar_no_asistio()

    def reagendar_cita(
        self,
        cita: Cita,
        medico: Medico,
        nueva_inicio: datetime,
        duracion_minutos: int = 30,
        ahora: datetime | None = None,
    ) -> Cita:
        """Reagenda la cita y registra la nueva en la agenda del médico."""
        nueva = cita.reagendar(nueva_inicio, duracion_minutos, ahora)
        medico.agenda.agregar_cita(nueva)
        return nueva

    # ── Visualización de agendas ──────────────────────────────────────────────

    def ver_agenda_medico(self, medico: Medico, fecha: date) -> list[Cita]:
        return medico.agenda.citas_del_dia(fecha)

    def slots_disponibles_medico(self, medico: Medico, fecha: date) -> list[datetime]:
        return medico.agenda.slots_disponibles(fecha)

    # ── Listas de espera ──────────────────────────────────────────────────────

    def agregar_a_lista_espera(self, lista: Lista_de_Espera, paciente: Paciente) -> bool:
        return lista.agregar_paciente_en_lista(paciente)

    def extraer_de_lista_espera(self, lista: Lista_de_Espera) -> Paciente | None:
        return lista.extraer_paciente_de_lista()

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
