"""Lista de espera de pacientes por especialidad."""


class Lista_de_Espera:

    def __init__(self, especialidad: Especialidad):
        self.especialidad = especialidad
        # Lista de tuplas: (Paciente, datetime_inscripcion) para mantener prioridad básica (FIFO: el que llega primero se atiende primero)
        self.pacientes_en_lista_de_espera: list[tuple[Paciente, datetime]] = []

    # Inscribe a un paciente en la lista de espera con la hora exacta en la que realiza la solicitud.
    # Si el paciente ya tiene una hora asignada en una especialidad, no es posible pedir otra en la misma especialidad.
    def agregar_paciente_en_lista(self, paciente: Paciente) -> bool:
        for i in self.pacientes_en_lista_de_espera:
            if i[0].RUN_usuario == paciente.RUN_usuario:
                return False
        self.pacientes_en_lista_de_espera.append((paciente, datetime.now()))
        return True
    
    # Saca de la lista de espera al paciente que lleva más tiempo esperando (priorización básica).
    def extraer_paciente_de_lista(self) -> Paciente | None:
        if len(self.pacientes_en_lista_de_espera) > 0:
            self.pacientes_en_lista_de_espera.sort(key=lambda x: x[1])
            paciente_prioritario = self.pacientes_en_lista_de_espera.pop(0)
            return paciente_prioritario[0]
        else:
            return None