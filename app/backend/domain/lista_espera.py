"""Lista de espera de pacientes por especialidad."""

from datetime import datetime

from typing import Optional
# Optional permitirá que el resultado final de una función pueda ser de diistintos tipos.

from app.backend.domain.usuarios import Paciente, Medico, Especialidad, Clinica
from app.backend.domain.enums import PrioridadEspera
from app.backend.domain.citas import Cita

# Definimos el peso de las prioridades para poder ordenarlas.
nivel_urgencia = {
    PrioridadEspera.URGENTE: 0,
    PrioridadEspera.ALTA: 1,
    PrioridadEspera.NORMAL: 2,
    PrioridadEspera.BAJA: 3
}

class Lista_de_Espera:

    def __init__(self, especialidad: Especialidad, clinica: Clinica):
        self.especialidad = especialidad
        self.clinica = clinica
        # Lista de tuplas: (Paciente, datetime_inscripcion, nivel_urgencia) para mantener prioridad básica.
        self.pacientes_en_lista_de_espera: list[tuple[Paciente, datetime, PrioridadEspera]] = []


    # Inscribe a un paciente en la lista de espera con la hora exacta en la que realiza la solicitud y el nivel de urgencia.
    # Si el paciente ya tiene una hora asignada en una especialidad, no es posible pedir otra en la misma especialidad.
    def agregar_paciente_en_lista(self, paciente: Paciente, prioridad: PrioridadEspera = PrioridadEspera.NORMAL, fecha_inscripcion: Optional[datetime] = None) -> bool:
    # Si el paciente no ingresa un nivel de urgencia el sistema lo toma como nivel NORMAL.
    # La fecha y hora puede ser la del momento de inscripción (datetime.now()) o la de reasignación.
    
        for i in self.pacientes_en_lista_de_espera:
            if i[0].RUN_usuario == paciente.RUN_usuario:
                return False  # El paciente ya está en la lista de espera de esta especialidad

        if fecha_inscripcion is None:
            fecha = datetime.now()
        else:
            fecha = fecha_inscripcion

        # Si el paciente no estaba inscrito en la lista, se inscribe. 
        self.pacientes_en_lista_de_espera.append((paciente, fecha, prioridad))
        return True
    

    # Saca de la lista de espera al paciente que lleva más tiempo esperando (priorización básica), considerando el nivel de urgencia.
    def extraer_paciente_de_lista(self) -> Optional[Paciente]:

        # Ordenamos primero por el peso de la prioridad y luego por la fecha de inscripción. 
        # El que lleva más tiempo esperando sale.
        if len(self.pacientes_en_lista_de_espera) > 0:
            self.pacientes_en_lista_de_espera.sort(key=lambda x: (nivel_urgencia[x[2]], x[1]))
            paciente_prioritario = self.pacientes_en_lista_de_espera.pop(0)
            return paciente_prioritario[0]
        
        else:
            return None
        

    # Confirma la disponibilidad de un paciente, acá en teroría se simula la interacción del paciente mediante telegram.
    # NO VERSIÓN FINAL, HASTA QUE INTERACTUEMOS CON TELEGRAM.
    def confirmar_disponibilidad(self, paciente: Paciente, fecha_hora_disponible: datetime, respuesta_simulada: str = "ACEPTA") -> str:

        print(f"Evaluando cupo del {fecha_hora_disponible} para {paciente.nombre}.")
        print(f"Respuesta simulada del paciente: {respuesta_simulada}")
        
        # Se valida y entrega una respuesta. Por defecto simulamos que responde que "ACEPTA". 
        return respuesta_simulada


    # Crea una cita real y la coloca en la agenda de un médico.
    def asignar_hora_disponible(self, paciente: Paciente, medico: Medico, inicio: datetime) -> None:
        
        # Creamos una nueva cita.
        nueva_cita = Cita.crear(
            paciente_id = paciente.RUN_usuario, 
            medico_id = medico.RUN_usuario,
            especialidad = self.especialidad.nombre,
            inicio = inicio,
            duracion_minutos = medico.agenda.duracion_slot_minutos,
            motivo = "Cupo asignado desde Lista de Espera"
        )
        
        # Guardardamos la cita en el calendario del médico.
        medico.agenda.agregar_cita(nueva_cita)
        print(f"Cupo asignado a {paciente.nombre} con Dr(a). {medico.nombre} el {inicio}.")


    # Si se libera un espacio entonces tratamos de asignarlo a un paciente en lista de espera.
    # NO VERSIÓN FINAL, HASTA QUE INTERACTUEMOS CON TELEGRAM.
    def liberar_reasignar_cupo_en_lista(self, medico: Medico, fecha_hora_libre: datetime, respuesta_simulada: str = "ACEPTA") -> bool:

        print(f"Se ha liberado un cupo el {fecha_hora_libre}. Revisando lista de espera de {self.especialidad.nombre}")
        
        # Guardamos en una lista a los pacientes que rechazaron este horario pero quieren seguir en la lista.
        pacientes_a_reinsertar = []
        cupo_asignado = False

        # Mientras haya gente en la fila y todavía no hayamos llenado el cupo, iteramos.
        while len(self.pacientes_en_lista_de_espera) > 0 and cupo_asignado == False:
            
            # En caso de que el paciente rechace pero quiera seguir en la lista, guardamos sus características para no perderlas.
            # Primero ordenamos la lista para que el método saque al paciente correcto.
            self.pacientes_en_lista_de_espera.sort(key=lambda x: (nivel_urgencia[x[2]], x[1]))
            info_prioritario = self.pacientes_en_lista_de_espera[0]

            # Extraemos sus características.
            fecha_original_actual = info_prioritario[1]
            prioridad = info_prioritario[2]
            
            # Ahora si sacamos al paciente prioritario de la lista.
            paciente_candidato = self.extraer_paciente_de_lista()
            
            if paciente_candidato is not None:
                respuesta = self.confirmar_disponibilidad(paciente_candidato, fecha_hora_libre, respuesta_simulada)
                
                if respuesta == "ACEPTA":
                    self.asignar_hora_disponible(paciente_candidato, medico, fecha_hora_libre) 
                    cupo_asignado = True
                    
                elif respuesta == "RECHAZA_PERO_MANTIENE":
                    print(f"{paciente_candidato.nombre} no puede en este horario, pero quiere seguir en la lista. Guardando")
                    # Lo guardamos en la lista temporal manteniendo su prioridad original.
                    pacientes_a_reinsertar.append((paciente_candidato, prioridad, fecha_original_actual))
                    cupo_asignado = False
                    
                elif respuesta == "RECHAZA_DEFINITIVAMENTE":
                    print(f"{paciente_candidato.nombre} ya no necesita la hora. Eliminado definitivamente de la lista de espera.")
                    # Pasa al siguiente en lista de espera.
                    cupo_asignado = False
        
        # Se devuelve a la lista oficial a todos los que dijeron que no podían, respetando su urgencia y fecha original.
        for paciente, urgencia, fecha in pacientes_a_reinsertar:
            self.agregar_paciente_en_lista(paciente, urgencia, fecha)
            
        return cupo_asignado
    
