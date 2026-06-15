"""Lista de espera de pacientes por especialidad."""

from datetime import datetime
from typing import Optional

from app.backend.domain.enums import PrioridadEspera
from app.backend.domain.especialidades import Especialidad
from app.backend.domain.usuarios import Paciente, Medico
from app.backend.domain.clinica import Clinica
from app.backend.domain.citas import Cita

# Peso numérico para ordenar la lista: menor número = mayor urgencia.
_PESO_PRIORIDAD = {
    PrioridadEspera.URGENTE: 0,
    PrioridadEspera.ALTA:    1,
    PrioridadEspera.NORMAL:  2,
    PrioridadEspera.BAJA:    3,
}


class Lista_de_Espera:
    """
    Cola de pacientes que esperan un cupo en una especialidad.
    El orden está dado por prioridad y, dentro del mismo nivel, por antigüedad.
    """

    def __init__(self, especialidad: Especialidad, clinica: Clinica):
        self.especialidad = especialidad
        self.clinica = clinica
        # Cada elemento: (Paciente, fecha_inscripcion, PrioridadEspera)
        self._cola: list[tuple[Paciente, datetime, PrioridadEspera]] = []

    def agregar_paciente_en_lista(
        self,
        paciente: Paciente,
        prioridad: PrioridadEspera = PrioridadEspera.NORMAL,
        fecha_inscripcion: Optional[datetime] = None,
    ) -> bool:
        """Inscribe al paciente. Devuelve False si ya estaba en la lista."""
        if any(e[0].RUN_usuario == paciente.RUN_usuario for e in self._cola):
            return False
        fecha = fecha_inscripcion if fecha_inscripcion is not None else datetime.now()
        self._cola.append((paciente, fecha, prioridad))
        return True

    def extraer_paciente_de_lista(self) -> Optional[Paciente]:
        """Saca y devuelve al paciente con mayor prioridad (y más tiempo esperando)."""
        if not self._cola:
            return None
        self._cola.sort(key=lambda x: (_PESO_PRIORIDAD[x[2]], x[1]))
        return self._cola.pop(0)[0]

    def confirmar_disponibilidad(
        self,
        paciente: Paciente,
        fecha_hora_disponible: datetime,
        respuesta_simulada: str = "ACEPTA",
    ) -> str:
        """
        Notifica al paciente sobre un cupo disponible y devuelve su respuesta.
        Por ahora simula la respuesta; en producción se integra con Telegram.
        """
        return respuesta_simulada

    def asignar_hora_disponible(self, paciente: Paciente, medico: Medico, inicio: datetime) -> None:
        """Crea la cita y la registra en la agenda del médico."""
        nueva_cita = Cita.crear(
            paciente_id=paciente.RUN_usuario,
            medico_id=medico.RUN_usuario,
            especialidad=self.especialidad.nombre,
            inicio=inicio,
            duracion_minutos=medico.agenda.duracion_slot_minutos,
            motivo="Cupo asignado desde Lista de Espera",
        )
        medico.agenda.agregar_cita(nueva_cita)

    def liberar_reasignar_cupo_en_lista(
        self,
        medico: Medico,
        fecha_hora_libre: datetime,
        respuesta_simulada: str = "ACEPTA",
    ) -> bool:
        """
        Intenta asignar el cupo liberado al siguiente paciente en espera.
        Devuelve True si se logró asignar el cupo.
        """
        pacientes_a_reinsertar: list[tuple[Paciente, PrioridadEspera, datetime]] = []
        cupo_asignado = False

        while self._cola and not cupo_asignado:
            self._cola.sort(key=lambda x: (_PESO_PRIORIDAD[x[2]], x[1]))
            info = self._cola[0]
            fecha_original, prioridad = info[1], info[2]
            paciente_candidato = self.extraer_paciente_de_lista()

            if paciente_candidato is None:
                break

            respuesta = self.confirmar_disponibilidad(paciente_candidato, fecha_hora_libre, respuesta_simulada)

            if respuesta == "ACEPTA":
                self.asignar_hora_disponible(paciente_candidato, medico, fecha_hora_libre)
                cupo_asignado = True
            elif respuesta == "RECHAZA_PERO_MANTIENE":
                pacientes_a_reinsertar.append((paciente_candidato, prioridad, fecha_original))

        for p, prio, fec in pacientes_a_reinsertar:
            self.agregar_paciente_en_lista(paciente=p, prioridad=prio, fecha_inscripcion=fec)

        return cupo_asignado
