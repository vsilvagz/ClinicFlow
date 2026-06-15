"""Lista de espera de pacientes por especialidad."""

# datetime: fecha y hora, ej: 2026-06-14 10:30. Lo usamos para saber cuándo se inscribió cada paciente.
from datetime import datetime

# Optional[T]: indica que el valor puede ser de tipo T o None (vacío).
from typing import Optional

# Importamos PrioridadEspera para saber el nivel de urgencia de cada paciente en espera.
from app.backend.domain.enums import PrioridadEspera

# Importamos Especialidad para asociar la lista a una especialidad concreta.
from app.backend.domain.especialidades import Especialidad

# Importamos Paciente y Medico para saber quién espera y quién atenderá.
from app.backend.domain.usuarios import Paciente, Medico

# Importamos Clinica para que la lista de espera sepa a qué clínica pertenece.
from app.backend.domain.clinica import Clinica

# Importamos Cita para poder crear una nueva cita cuando se asigne un cupo.
from app.backend.domain.citas import Cita


# Diccionario que asigna un número de peso a cada nivel de prioridad.
# Número más bajo = mayor urgencia (sale primero de la lista).
nivel_urgencia = {
    PrioridadEspera.URGENTE: 0,  # Urgente sale primero (peso 0).
    PrioridadEspera.ALTA:    1,  # Alta urgencia (peso 1).
    PrioridadEspera.NORMAL:  2,  # Prioridad normal (peso 2).
    PrioridadEspera.BAJA:    3,  # Baja prioridad (peso 3, sale último).
}


# Lista_de_Espera gestiona la cola de pacientes que esperan una hora en una especialidad.
# Cuando hay cancelaciones o cupos nuevos, se extrae al primero de la lista considerando urgencia y tiempo de espera.
class Lista_de_Espera:

    # __init__ es el constructor: se ejecuta al crear la lista de espera.
    def __init__(self, especialidad: Especialidad, clinica: Clinica):
        self.especialidad = especialidad  # La especialidad a la que pertenece esta lista.
        self.clinica = clinica            # La clínica donde funciona esta lista de espera.
        # Lista de tuplas de tres elementos: (Paciente, datetime_inscripcion, PrioridadEspera).
        # Una tupla es como un grupo de datos fijo, ej: (paciente_juan, "10:30 del martes", URGENTE).
        # Guardamos la hora y la prioridad para ordenar quién sale primero.
        self.pacientes_en_lista_de_espera: list[tuple[Paciente, datetime, PrioridadEspera]] = []

    # Inscribe a un paciente en la lista de espera con la hora exacta y el nivel de urgencia.
    # Si el paciente ya tiene una hora asignada en esta especialidad, no se puede agregar de nuevo.
    def agregar_paciente_en_lista(
        self,
        paciente: Paciente,                               # El paciente que quiere entrar a la lista.
        prioridad: PrioridadEspera = PrioridadEspera.NORMAL,  # Nivel de urgencia (NORMAL por defecto).
        fecha_inscripcion: Optional[datetime] = None,    # Hora de inscripción (None = usar la hora actual).
    ) -> bool:
        """Inscribe al paciente en la lista. Devuelve False si ya estaba inscrito."""
        # Si el paciente no ingresa un nivel de urgencia, el sistema lo toma como nivel NORMAL.
        # La fecha y hora puede ser la del momento de inscripción (datetime.now()) o la de reasignación.
        for i in self.pacientes_en_lista_de_espera:  # Recorremos la lista actual.
            if i[0].RUN_usuario == paciente.RUN_usuario:  # i[0] es el Paciente de cada tupla.
                return False  # El paciente ya estaba en la lista; no lo agregamos dos veces.

        # Si no se pasó una fecha, usamos la hora exacta en que se llama a este método.
        if fecha_inscripcion is None:
            fecha = datetime.now()
        else:
            fecha = fecha_inscripcion  # Si se pasó una fecha específica, la usamos.

        # Si el paciente no estaba inscrito en la lista, lo inscribimos.
        self.pacientes_en_lista_de_espera.append((paciente, fecha, prioridad))
        return True  # Devolvemos True para indicar que se inscribió correctamente.

    # Saca de la lista al paciente con mayor urgencia y, entre los de igual urgencia, al que lleva más tiempo esperando.
    def extraer_paciente_de_lista(self) -> Optional[Paciente]:
        """Saca y devuelve al paciente con mayor prioridad (y más tiempo esperando). None si la lista está vacía."""
        if len(self.pacientes_en_lista_de_espera) > 0:  # Solo actuamos si hay alguien esperando.
            # Ordenamos primero por el peso de la prioridad y luego por la fecha de inscripción.
            # lambda x: (nivel_urgencia[x[2]], x[1]) = "ordena por prioridad y luego por fecha".
            self.pacientes_en_lista_de_espera.sort(key=lambda x: (nivel_urgencia[x[2]], x[1]))
            # pop(0) saca y elimina el primer elemento de la lista (el prioritario).
            paciente_prioritario = self.pacientes_en_lista_de_espera.pop(0)
            return paciente_prioritario[0]  # Devolvemos solo el Paciente (no la fecha ni la prioridad).
        else:
            return None  # Si la lista está vacía, devolvemos None (no hay nadie esperando).

    # Confirma la disponibilidad de un paciente; simula la interacción del paciente mediante Telegram.
    # NOTA: NO ES VERSIÓN FINAL, hasta que integremos con Telegram real.
    def confirmar_disponibilidad(
        self,
        paciente: Paciente,              # El paciente al que le estamos preguntando.
        fecha_hora_disponible: datetime, # La fecha y hora del cupo disponible.
        respuesta_simulada: str = "ACEPTA",  # Simulamos que el paciente responde "ACEPTA" por defecto.
    ) -> str:
        """Simula la notificación y respuesta del paciente ante un cupo disponible. Devuelve la respuesta."""
        print(f"Evaluando cupo del {fecha_hora_disponible} para {paciente.nombre}.")
        print(f"Respuesta simulada del paciente: {respuesta_simulada}")
        # En la versión final, aquí se enviará un mensaje por Telegram y se esperará la respuesta real.
        return respuesta_simulada  # Devolvemos la respuesta simulada tal como llegó.

    # Crea una cita real y la coloca en la agenda del médico seleccionado.
    def asignar_hora_disponible(
        self,
        paciente: Paciente,   # El paciente que recibirá el cupo.
        medico: Medico,       # El médico que atenderá la cita.
        inicio: datetime,     # La fecha y hora del cupo a asignar.
    ) -> None:
        """Crea la cita y la registra en la agenda del médico."""
        # Usamos el factory method Cita.crear() para construir la cita correctamente.
        nueva_cita = Cita.crear(
            paciente_id=paciente.RUN_usuario,              # RUN del paciente.
            medico_id=medico.RUN_usuario,                  # RUN del médico.
            especialidad=self.especialidad.nombre,          # Nombre de la especialidad de esta lista.
            inicio=inicio,                                  # Fecha y hora de inicio.
            duracion_minutos=medico.agenda.duracion_slot_minutos,  # Duración según la agenda del médico.
            motivo="Cupo asignado desde Lista de Espera",  # Motivo estándar para estos casos.
        )
        # Registramos la cita en el calendario del médico (valida solapamiento, horario, etc.).
        medico.agenda.agregar_cita(nueva_cita)
        print(f"Cupo asignado a {paciente.nombre} con Dr(a). {medico.nombre} el {inicio}.")

    # Si se libera un espacio, trata de asignarlo a alguien de la lista de espera.
    # NOTA: NO ES VERSIÓN FINAL, hasta que integremos con Telegram real.
    def liberar_reasignar_cupo_en_lista(
        self,
        medico: Medico,                          # El médico que tiene el cupo libre.
        fecha_hora_libre: datetime,              # La fecha y hora del cupo que se liberó.
        respuesta_simulada: str = "ACEPTA",      # Respuesta simulada del paciente (por defecto acepta).
    ) -> bool:
        """Intenta asignar el cupo liberado al paciente prioritario. Devuelve True si se pudo asignar."""
        print(f"Se ha liberado un cupo el {fecha_hora_libre}. Revisando lista de espera de {self.especialidad.nombre}")

        # Lista temporal para guardar a los pacientes que rechazaron este horario pero quieren seguir en espera.
        pacientes_a_reinsertar = []
        cupo_asignado = False  # Bandera para saber si ya asignamos el cupo.

        # Mientras haya gente en la fila y todavía no hayamos llenado el cupo, seguimos iterando.
        while len(self.pacientes_en_lista_de_espera) > 0 and cupo_asignado == False:

            # Ordenamos la lista para que siempre saquemos al paciente correcto (por prioridad y fecha).
            self.pacientes_en_lista_de_espera.sort(key=lambda x: (nivel_urgencia[x[2]], x[1]))
            # Guardamos los datos del candidato ANTES de sacarlo, para poder reinsertarlo si rechaza.
            info_prioritario = self.pacientes_en_lista_de_espera[0]
            fecha_original_actual = info_prioritario[1]  # Fecha original de inscripción.
            prioridad = info_prioritario[2]              # Prioridad original del paciente.

            # Sacamos al candidato más prioritario de la lista.
            paciente_candidato = self.extraer_paciente_de_lista()

            if paciente_candidato is not None:  # Si había alguien en la lista...
                # Le preguntamos si puede en ese horario (simulado por ahora).
                respuesta = self.confirmar_disponibilidad(paciente_candidato, fecha_hora_libre, respuesta_simulada)

                if respuesta == "ACEPTA":
                    # El paciente acepta: le creamos la cita en la agenda del médico.
                    self.asignar_hora_disponible(paciente_candidato, medico, fecha_hora_libre)
                    cupo_asignado = True  # Marcamos que el cupo ya fue asignado.

                elif respuesta == "RECHAZA_PERO_MANTIENE":
                    # El paciente no puede en este horario, pero quiere seguir en la lista.
                    print(f"{paciente_candidato.nombre} no puede en este horario, pero quiere seguir en la lista. Guardando")
                    # Lo guardamos en la lista temporal manteniendo su prioridad y fecha originales.
                    pacientes_a_reinsertar.append((paciente_candidato, prioridad, fecha_original_actual))
                    cupo_asignado = False  # Seguimos buscando al siguiente en la lista.

                elif respuesta == "RECHAZA_DEFINITIVAMENTE":
                    # El paciente ya no necesita la hora: lo eliminamos definitivamente.
                    print(f"{paciente_candidato.nombre} ya no necesita la hora. Eliminado definitivamente de la lista de espera.")
                    cupo_asignado = False  # Continuamos con el siguiente en la lista.

        # Devolvemos a la lista oficial a todos los que dijeron que no podían, respetando su urgencia y fecha original.
        for p, prio, fec in pacientes_a_reinsertar:
            self.agregar_paciente_en_lista(paciente=p, prioridad=prio, fecha_inscripcion=fec)

        return cupo_asignado  # True si se asignó el cupo, False si la lista estaba vacía o todos rechazaron.
