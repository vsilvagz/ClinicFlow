from lista_espera import Lista_de_Espera
from agenda import BloqueHorario, Bloqueo, Suspension, Agenda
from usuarios import Usuario, Paciente, Especialidad, Medico, Clinica, Recepcionista, Administrador
from citas import Cita
from enums import EstadoCita, RolUsuario, PrioridadEspera, EstadoDerivacion
from errores import (
    ClinicFlowError, TransicionEstadoInvalida, CitaEnPasadoError, ConflictoDeAgenda,
    HorarioNoDisponible, AgendaSuspendida, CitaNoEncontrada, PacienteNoEncontrado,
    MedicoNoEncontrado, PermisoDenegado, ListaEsperaLlena, PacienteYaEnEspera,
    DerivacionNoEncontrada, DerivacionExpirada, DerivacionYaUsada
)
from derivacion import Derivacion


#Medico(Usuario):
#    def __init__(self, RUN_usuario: int, nombre: str, correo: str, telefono: int, especialidad):

medico_1 = Medico(12345678, "Juan Pérez", "dr.juan.perez@clinica.com", 987654321, "Cardiología")

medico_1.especialidad()
