"""Tipos de usuario del sistema y sus permisos."""

# Permite usar tipos de la propia clase dentro de sus métodos sin errores de Python.
from __future__ import annotations

# date: solo fecha, ej: 2026-06-14. datetime: fecha y hora, ej: 2026-06-14 10:30.
from datetime import date, datetime

# TYPE_CHECKING: bloque que solo se evalúa al revisar tipos, no al ejecutar.
# Sirve para evitar importaciones circulares (A importa B, B importa A).
from typing import TYPE_CHECKING

# Importamos las clases que los usuarios necesitan para funcionar.
from app.backend.domain.agenda import Agenda, Bloqueo, Suspension  # Agenda del médico.
from app.backend.domain.citas import Cita                          # Citas médicas.
from app.backend.domain.derivacion import Derivacion               # Derivaciones entre especialidades.
from app.backend.domain.especialidades import Especialidad         # Especialidad médica.

# Lista_de_Espera se importa SOLO para revisión de tipos (no en ejecución),
# para evitar un ciclo: usuarios.py importa lista_espera.py que importa usuarios.py.
if TYPE_CHECKING:
    from app.backend.domain.lista_espera import Lista_de_Espera


# ──────────────────────────────────────────────────────────────────────────────
# CLASE BASE: Usuario
# Contiene los datos comunes a todos los tipos de usuario del sistema.
# Las demás clases (Paciente, Medico, etc.) heredan de esta.
# ──────────────────────────────────────────────────────────────────────────────

class Usuario:
    # __init__ es el constructor: se ejecuta al crear un objeto Usuario (o de cualquier subclase).
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        self.__RUN_usuario = RUN_usuario  # Doble guión bajo (__): atributo privado, no accesible desde fuera.
        self._nombre = nombre             # Un guión bajo (_): atributo protegido, accesible a subclases.
        self._correo = correo             # Correo electrónico del usuario.
        self._telefono = telefono         # Teléfono de contacto.

    @property  # RUN_usuario es de solo lectura: no se puede cambiar después de creado.
    def RUN_usuario(self) -> int:
        return self.__RUN_usuario  # Devuelve el RUN almacenado en el atributo privado.

    @property
    def nombre(self) -> str:
        return self._nombre  # Devuelve el nombre del usuario.

    @nombre.setter  # Permite cambiar el nombre desde fuera de la clase.
    def nombre(self, valor: str):
        self._nombre = valor  # Actualiza el nombre con el nuevo valor.

    @property
    def correo(self) -> str:
        return self._correo  # Devuelve el correo del usuario.

    @correo.setter
    def correo(self, valor: str):
        if "@" not in valor:  # Validación básica: todo correo debe tener un "@".
            raise ValueError("El correo no es válido.")
        self._correo = valor  # Si el correo es válido, lo actualizamos.

    @property
    def telefono(self) -> int:
        return self._telefono  # Devuelve el teléfono del usuario.

    @telefono.setter
    def telefono(self, valor: int):
        self._telefono = valor  # Actualiza el teléfono con el nuevo valor.


# ──────────────────────────────────────────────────────────────────────────────
# Paciente: puede pedir, cancelar y reagendar sus propias citas,
# e interactuar con el sistema mediante Telegram.
# ──────────────────────────────────────────────────────────────────────────────

# Paciente solo puede hacer cosas relacionadas con sus propias citas, además de interactuar con Telegram.
class Paciente(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)  # Llama al __init__ de Usuario.
        self._derivaciones_especialidades_permitidas: list[str] = []  # Lista de especialidades habilitadas por derivación médica.
        # Si un médico activó una derivación, esta queda validada dentro de la lista para que el sistema pueda aprobar una hora en dicha especialidad.
        self._citas: list[Cita] = []  # Lista de todas las citas del paciente (activas e historial).

    @property
    def derivaciones_especialidades_permitidas(self) -> list[str]:
        return list(self._derivaciones_especialidades_permitidas)  # Devuelve una copia para no exponer la lista interna.

    def agregar_derivacion(self, especialidad: str) -> None:
        """Habilita al paciente para agendar en una especialidad gracias a una derivación."""
        self._derivaciones_especialidades_permitidas.append(especialidad)  # Agrega la especialidad a la lista.

    def registrar_cita(self, cita: Cita) -> None:
        """Asocia una cita al historial del paciente."""
        self._citas.append(cita)  # Agrega la cita a la lista interna del paciente.

    def citas_activas(self) -> list[Cita]:
        """Devuelve solo las citas que están en estado PENDIENTE o CONFIRMADA."""
        return [c for c in self._citas if c.esta_activa]  # Filtra usando la propiedad esta_activa de Cita.

    def tiene_cita_en_especialidad(self, especialidad: str) -> bool:
        """Devuelve True si el paciente ya tiene una cita activa en esa especialidad."""
        return any(c.especialidad == especialidad for c in self.citas_activas())  # Busca en las citas activas.

    def historial_citas(self) -> list[Cita]:
        """Devuelve todas las citas del paciente (activas, canceladas, completadas, etc.)."""
        return list(self._citas)  # Devuelve una copia de la lista completa.


# ──────────────────────────────────────────────────────────────────────────────
# Medico: gestiona su propia agenda, emite derivaciones y ve info de sus pacientes.
# La Agenda vive DENTRO del Médico (composición).
# ──────────────────────────────────────────────────────────────────────────────

# Médico solo puede hacer cosas relacionadas con su propia agenda, además de ver info de sus pacientes y derivaciones.
class Medico(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, especialidad: Especialidad):
        super().__init__(RUN_usuario, nombre, correo, telefono)  # Llama al __init__ de Usuario.
        self._especialidad = especialidad          # Especialidad médica del médico.
        self._agenda: Agenda = Agenda()            # Cada médico tiene su propia agenda (composición).
        self._derivaciones_emitidas: list[Derivacion] = []  # Lista de derivaciones que ha emitido este médico.

    @property
    def especialidad(self) -> Especialidad:
        return self._especialidad  # Devuelve la especialidad del médico.

    @especialidad.setter
    def especialidad(self, valor: Especialidad):
        self._especialidad = valor  # Permite cambiar la especialidad del médico.

    @property
    def agenda(self) -> Agenda:
        return self._agenda  # Devuelve la agenda del médico para que otros la consulten.

    def bloquear_horario(self, inicio: datetime, fin: datetime, motivo: str = "") -> Bloqueo:
        """El médico bloquea un intervalo de su agenda (sin cancelar citas existentes)."""
        return self._agenda.bloquear(inicio, fin, motivo)  # Delega la operación a su Agenda.

    def suspender_agenda(self, inicio: datetime, fin: datetime, motivo: str = "") -> tuple[Suspension, list[Cita]]:
        """El médico suspende toda su agenda en un período; cancela las citas activas afectadas."""
        return self._agenda.suspender(inicio, fin, motivo)  # Delega a la Agenda; devuelve las citas canceladas.

    def registrar_derivacion(self, derivacion: Derivacion) -> None:
        """Guarda en el historial del médico una derivación que él emitió."""
        self._derivaciones_emitidas.append(derivacion)  # Agrega la derivación a su lista.

    def derivaciones_vigentes(self) -> list[Derivacion]:
        """Devuelve las derivaciones que aún están activas (PENDIENTE o ACEPTADA)."""
        return [d for d in self._derivaciones_emitidas if d.esta_activa]  # Filtra por estado activo.

    def historial_derivaciones(self) -> list[Derivacion]:
        """Devuelve todas las derivaciones que el médico ha emitido (activas y cerradas)."""
        return list(self._derivaciones_emitidas)  # Devuelve una copia de la lista completa.


# ──────────────────────────────────────────────────────────────────────────────
# Recepcionista: gestiona citas de los pacientes y agendas de los médicos
# de la clínica en la que trabaja.
# ──────────────────────────────────────────────────────────────────────────────

# Recepcionista puede hacer cosas relacionadas con las agendas de los médicos de su clínica y las citas de los pacientes.
# Pueden gestionar citas, reagendar pacientes, administrar listas de espera y visualizar agendas clínicas.
class Recepcionista(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, clinica):
        super().__init__(RUN_usuario, nombre, correo, telefono)  # Llama al __init__ de Usuario.
        self._clinica = clinica  # La clínica en la que trabaja este/a recepcionista.
        # El/La recepcionista trabaja en una clínica específica (Enunciado especifica "Administrar clínicas").
        # Útil si por ejemplo hay distintas sucursales.

    @property
    def clinica(self):
        return self._clinica  # Devuelve la clínica a la que pertenece.

    @clinica.setter
    def clinica(self, valor):
        self._clinica = valor  # Permite cambiar la clínica (ej: traslado de sucursal).

    # ── Gestión de citas ──────────────────────────────────────────────────────

    def confirmar_cita(self, cita: Cita) -> None:
        """La recepcionista confirma una cita: cambia su estado de PENDIENTE a CONFIRMADA."""
        cita.confirmar()  # Delega la operación al método confirmar() de la Cita.

    def cancelar_cita(self, cita: Cita) -> None:
        """La recepcionista cancela una cita: cambia su estado a CANCELADA."""
        cita.cancelar()  # Delega al método cancelar() de la Cita.

    def marcar_no_asistio(self, cita: Cita) -> None:
        """Registra que el paciente no se presentó: cambia el estado a NO_ASISTIO."""
        cita.marcar_no_asistio()  # Delega al método marcar_no_asistio() de la Cita.

    def reagendar_cita(
        self,
        cita: Cita,                        # La cita original que se quiere reagendar.
        medico: Medico,                    # El médico dueño de la agenda.
        nueva_inicio: datetime,            # Nueva fecha y hora propuesta.
        duracion_minutos: int = 30,        # Duración de la nueva cita (30 min por defecto).
        ahora: datetime | None = None,     # Hora de referencia (útil para tests).
    ) -> Cita:
        """Reagenda la cita y registra la nueva en la agenda del médico."""
        nueva = cita.reagendar(nueva_inicio, duracion_minutos, ahora)  # Crea la nueva cita.
        medico.agenda.agregar_cita(nueva)  # La agrega a la agenda del médico con todas sus validaciones.
        return nueva  # Devuelve la nueva cita para que el sistema la pueda usar.

    # ── Visualización de agendas ──────────────────────────────────────────────

    def ver_agenda_medico(self, medico: Medico, fecha: date) -> list[Cita]:
        """Devuelve todas las citas de un médico en una fecha específica."""
        return medico.agenda.citas_del_dia(fecha)  # Delega a la Agenda del médico.

    def slots_disponibles_medico(self, medico: Medico, fecha: date) -> list[datetime]:
        """Devuelve la lista de horarios disponibles de un médico en una fecha."""
        return medico.agenda.slots_disponibles(fecha)  # Delega a la Agenda del médico.

    # ── Listas de espera ──────────────────────────────────────────────────────

    def agregar_a_lista_espera(self, lista: Lista_de_Espera, paciente: Paciente) -> bool:
        """Inscribe al paciente en la lista de espera. Devuelve False si ya estaba."""
        return lista.agregar_paciente_en_lista(paciente)  # Delega a la Lista_de_Espera.

    def extraer_de_lista_espera(self, lista: Lista_de_Espera) -> Paciente | None:
        """Saca al paciente con más tiempo esperando de la lista. Devuelve None si está vacía."""
        return lista.extraer_paciente_de_lista()  # Delega a la Lista_de_Espera.


# ──────────────────────────────────────────────────────────────────────────────
# Administrador: acceso completo a todo el sistema.
# ──────────────────────────────────────────────────────────────────────────────

# Administrador(a) tiene acceso completo al sistema.
class Administrador(Usuario):
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)  # Llama al __init__ de Usuario.
        self.__acceso_vip = True  # Atributo privado que marca el acceso total al sistema.
        # Acceso total para administrar, configurar y visualizar todo el sistema.
        # ESTA ÚLTIMA VARIABLE SERÁ ÚTIL EN EL FUTURO PARA DARLE AL RECEPCIONISTA LOS PERMISOS CORRESPONDIENTES.

    @property
    def acceso_vip(self) -> bool:
        return self.__acceso_vip  # Devuelve True siempre (el administrador siempre tiene acceso total).
