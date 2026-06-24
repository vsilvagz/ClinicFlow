"""Tipos de usuario del sistema y sus permisos."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from app.backend.domain.agenda import Agenda, Bloqueo, Suspension
from app.backend.domain.citas import Cita
from app.backend.domain.derivacion import Derivacion, DIAS_VIGENCIA_DEFAULT
from app.backend.domain.enums import PrioridadEspera
from app.backend.domain.especialidades import Especialidad

if TYPE_CHECKING:
    from app.backend.domain.lista_espera import Lista_de_Espera
    from app.backend.domain.clinica import Clinica  # evita importación circular


class Usuario:
    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        self.__RUN_usuario = RUN_usuario
        self._nombre = nombre
        self._correo = correo
        self._telefono = telefono
        self._activo = True

    @property
    def RUN_usuario(self) -> int:
        return self.__RUN_usuario

    @property
    def activo(self) -> bool:
        """Indica si el usuario está habilitado (puede iniciar sesión y operar)."""
        return self._activo

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
    """
    Enunciado 3.2 — el paciente puede:
    solicitar citas, cancelar horas, reagendar,
    consultar disponibilidad e ingresar a listas de espera.
    Puede tener múltiples citas activas simultáneamente.
    """

    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._citas: list[Cita] = []

    # ── Solicitar / cancelar / reagendar ─────────────────────────────────────

    def solicitar_cita(
        self,
        medico: Medico,
        inicio: datetime,
        duracion_minutos: int = 30,
        motivo: str = "",
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """Crea la cita, la registra en la agenda del médico y en el historial propio."""
        cita = Cita.crear(
            paciente_id=self.RUN_usuario,
            medico_id=medico.RUN_usuario,
            especialidad=medico.especialidad.nombre,
            inicio=inicio,
            duracion_minutos=duracion_minutos,
            motivo=motivo,
            ahora=ahora,
        )
        medico.agenda.agregar_cita(cita)
        self._citas.append(cita)
        return cita

    def cancelar_cita(self, cita: Cita) -> None:
        """El paciente cancela una de sus citas."""
        cita.cancelar()

    def reagendar_cita(
        self,
        cita: Cita,
        medico: Medico,
        nueva_inicio: datetime,
        duracion_minutos: int = 30,
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """Reagenda una cita, registra la nueva en la agenda del médico y en el historial propio."""
        nueva = cita.reagendar(nueva_inicio, duracion_minutos, ahora)
        medico.agenda.agregar_cita(nueva)
        self._citas.append(nueva)
        return nueva

    # ── Consultar disponibilidad ──────────────────────────────────────────────

    def consultar_disponibilidad(self, medico: Medico, fecha: date) -> list[datetime]:
        """Devuelve los slots libres del médico en una fecha."""
        return medico.agenda.slots_disponibles(fecha)

    # ── Lista de espera ───────────────────────────────────────────────────────

    def inscribirse_en_lista_espera(
        self,
        lista: Lista_de_Espera,
        prioridad: PrioridadEspera = PrioridadEspera.NORMAL,
    ) -> bool:
        """Ingresa al paciente a la lista de espera. Devuelve False si ya estaba."""
        return lista.agregar_paciente_en_lista(self, prioridad)

    # ── Historial ─────────────────────────────────────────────────────────────

    def registrar_cita(self, cita: Cita) -> None:
        """Vincula una cita al historial del paciente (usada por recepcionista/servicio)."""
        self._citas.append(cita)

    def citas_activas(self) -> list[Cita]:
        return [c for c in self._citas if c.esta_activa]

    def tiene_cita_en_especialidad(self, especialidad: str) -> bool:
        return any(c.especialidad == especialidad for c in self.citas_activas())

    def historial_citas(self) -> list[Cita]:
        return list(self._citas)


class Medico(Usuario):
    """
    Enunciado 3.2 — el médico puede:
    visualizar su agenda, bloquear horarios, suspender atención
    y revisar información de sus pacientes y derivaciones.
    """

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

    # ── Gestión de agenda ─────────────────────────────────────────────────────

    def bloquear_horario(self, inicio: datetime, fin: datetime, motivo: str = "") -> Bloqueo:
        return self._agenda.bloquear(inicio, fin, motivo)

    def suspender_agenda(self, inicio: datetime, fin: datetime, motivo: str = "") -> tuple[Suspension, list[Cita]]:
        return self._agenda.suspender(inicio, fin, motivo)

    # ── Derivaciones ──────────────────────────────────────────────────────────

    def emitir_derivacion(
        self,
        paciente_id: int,
        especialidad_destino: str,
        motivo: str,
        dias_vigencia: int = DIAS_VIGENCIA_DEFAULT,
        medico_destino_id: Optional[int] = None,
        notas: Optional[str] = None,
        ahora: Optional[datetime] = None,
    ) -> Derivacion:
        """El médico activa la derivación (enunciado 3.1.4)."""
        derivacion = Derivacion.crear(
            paciente_id=paciente_id,
            medico_origen_id=self.RUN_usuario,
            especialidad_destino=especialidad_destino,
            motivo=motivo,
            dias_vigencia=dias_vigencia,
            medico_destino_id=medico_destino_id,
            notas=notas,
            ahora=ahora,
        )
        self._derivaciones_emitidas.append(derivacion)
        return derivacion

    def derivaciones_vigentes(self) -> list[Derivacion]:
        return [d for d in self._derivaciones_emitidas if d.esta_activa]

    def historial_derivaciones(self) -> list[Derivacion]:
        return list(self._derivaciones_emitidas)

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Medico):
            return NotImplemented
        return self.RUN_usuario == otro.RUN_usuario

    def __hash__(self) -> int:
        return hash(self.RUN_usuario)


class Recepcionista(Usuario):
    """
    Enunciado 3.2 — la recepcionista puede:
    gestionar citas, reagendar pacientes, administrar listas de espera
    y visualizar agendas clínicas.
    """

    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, clinica: Clinica):
        super().__init__(RUN_usuario, nombre, correo, telefono)
        self._clinica = clinica

    @property
    def clinica(self) -> Clinica:
        return self._clinica

    @clinica.setter
    def clinica(self, valor: Clinica):
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


class Administrador(Usuario):
    """Acceso completo al sistema.

    Administra usuarios, especialidades, clínicas, agendas y citas. Igual que los
    demás roles, sus métodos operan sobre objetos de dominio recibidos como
    parámetro; la traducción a/desde la base de datos la hace la capa de servicios.
    """

    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int):
        super().__init__(RUN_usuario, nombre, correo, telefono)

    # ── Gestión de usuarios ───────────────────────────────────────────────────

    def editar_usuario(
        self,
        usuario: Usuario,
        nombre: Optional[str] = None,
        correo: Optional[str] = None,
        telefono: Optional[int] = None,
    ) -> None:
        """Actualiza los datos de contacto de cualquier usuario.

        Solo toca los campos entregados; el correo se valida en su setter.
        """
        if nombre is not None:
            usuario.nombre = nombre
        if correo is not None:
            usuario.correo = correo
        if telefono is not None:
            usuario.telefono = telefono

    def desactivar_usuario(self, usuario: Usuario) -> None:
        """Da de baja a un usuario para que no pueda iniciar sesión ni operar."""
        if usuario.RUN_usuario == self.RUN_usuario:
            raise ValueError("Un administrador no puede desactivarse a sí mismo.")
        usuario._activo = False

    def reactivar_usuario(self, usuario: Usuario) -> None:
        """Vuelve a habilitar a un usuario dado de baja."""
        usuario._activo = True

    # ── Especialidades ────────────────────────────────────────────────────────

    def crear_especialidad(self, nombre: str, descripcion: str = "") -> Especialidad:
        """Crea una especialidad nueva del catálogo."""
        if not nombre or not nombre.strip():
            raise ValueError("La especialidad debe tener un nombre.")
        return Especialidad(nombre.strip(), descripcion.strip())

    def editar_especialidad(
        self,
        especialidad: Especialidad,
        nombre: Optional[str] = None,
        descripcion: Optional[str] = None,
    ) -> None:
        """Renombra o cambia la descripción de una especialidad existente."""
        if nombre is not None:
            if not nombre.strip():
                raise ValueError("La especialidad debe tener un nombre.")
            especialidad.nombre = nombre.strip()
        if descripcion is not None:
            especialidad.descripcion = descripcion.strip()

    # ── Clínicas ──────────────────────────────────────────────────────────────

    def crear_clinica(
        self,
        RUT_empresa: str,
        nombre: str,
        direccion: str = "Dirección no especificada",
    ) -> "Clinica":
        """Da de alta una clínica (sucursal)."""
        # Import diferido: clinica.py importa este módulo, así se evita el ciclo.
        from app.backend.domain.clinica import Clinica

        if not RUT_empresa or not str(RUT_empresa).strip():
            raise ValueError("La clínica debe tener un RUT.")
        if not nombre or not nombre.strip():
            raise ValueError("La clínica debe tener un nombre.")
        return Clinica(str(RUT_empresa).strip(), nombre.strip(), direccion.strip())

    def editar_clinica(
        self,
        clinica: "Clinica",
        nombre: Optional[str] = None,
        direccion: Optional[str] = None,
    ) -> None:
        """Actualiza el nombre o la dirección de una clínica."""
        if nombre is not None:
            if not nombre.strip():
                raise ValueError("La clínica debe tener un nombre.")
            clinica.nombre = nombre.strip()
        if direccion is not None:
            clinica.direccion = direccion.strip()

    # ── Agendas (sobre cualquier médico) ──────────────────────────────────────

    def bloquear_horario_de(
        self, medico: Medico, inicio: datetime, fin: datetime, motivo: str = ""
    ) -> Bloqueo:
        """Bloquea un tramo en la agenda de un médico."""
        return medico.bloquear_horario(inicio, fin, motivo)

    def suspender_agenda_de(
        self, medico: Medico, inicio: datetime, fin: datetime, motivo: str = ""
    ) -> tuple[Suspension, list[Cita]]:
        """Suspende la agenda de un médico en un período; cancela las citas activas."""
        return medico.suspender_agenda(inicio, fin, motivo)

    # ── Gestión de citas (acceso completo) ────────────────────────────────────

    def confirmar_cita(self, cita: Cita) -> None:
        cita.confirmar()

    def cancelar_cita(self, cita: Cita) -> None:
        cita.cancelar()

    def reagendar_cita(
        self,
        cita: Cita,
        medico: Medico,
        nueva_inicio: datetime,
        duracion_minutos: int = 30,
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """Mueve una cita a una nueva hora y la registra en la agenda del médico."""
        nueva = cita.reagendar(nueva_inicio, duracion_minutos, ahora)
        medico.agenda.agregar_cita(nueva)
        return nueva
