"""Modelos ORM (SQLAlchemy) de persistencia.

Importar las clases aquí cumple dos objetivos:

1. Que todos los modelos queden REGISTRADOS en `Base.metadata`. Esto es lo que
   permite a Alembic (migraciones) y a `create_all()` "ver" todas las tablas.
   Si un modelo no se importa en alguna parte, su tabla no se crea.
2. Ofrecer un punto único de importación: `from app.backend.models import MedicoORM`.
"""

from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import (
    AdministradorORM,
    MedicoORM,
    PacienteORM,
    RecepcionistaORM,
    UsuarioORM,
)
from app.backend.models.clinica import (
    ClinicaORM,
    clinica_especialidades,
    clinica_medicos,
)
from app.backend.models.agenda import (
    AgendaORM,
    BloqueHorarioORM,
    BloqueoORM,
    SuspensionORM,
)
from app.backend.models.citas import CitaORM
from app.backend.models.derivacion import DerivacionORM
from app.backend.models.lista_espera import (
    InscripcionEsperaORM,
    ListaEsperaORM,
)

# __all__ declara qué nombres se exportan con `from ...models import *`.
__all__ = [
    # Usuarios y especialidades
    "EspecialidadORM",
    "UsuarioORM",
    "PacienteORM",
    "MedicoORM",
    "RecepcionistaORM",
    "AdministradorORM",
    # Clínica y asociaciones
    "ClinicaORM",
    "clinica_medicos",
    "clinica_especialidades",
    # Agenda
    "AgendaORM",
    "BloqueHorarioORM",
    "BloqueoORM",
    "SuspensionORM",
    # Citas y derivaciones
    "CitaORM",
    "DerivacionORM",
    # Lista de espera
    "ListaEsperaORM",
    "InscripcionEsperaORM",
]
