"""Modelo ORM de una oferta de cupo liberado a un paciente en lista de espera.

Cuando se libera una hora (se cancela una cita o se suspende una agenda), el
sistema busca la primera hora disponible de la especialidad y la OFRECE al
paciente con mayor prioridad de la lista de espera. La oferta queda PENDIENTE
hasta que el paciente responde desde «Mis mensajes»:

  - la acepta  → se crea su cita (en estado PENDIENTE) y sale de la lista;
  - la rechaza → sigue esperando (la hora pasa al siguiente en la cola) o bien
    sale de la lista de espera.

Es una tabla aparte de `mensajes` (que son notificaciones de solo texto) porque
la oferta necesita datos ESTRUCTURADOS —médico, hora, duración, lista— para poder
concretar la reserva cuando el paciente la acepta. Se guarda el nombre del médico
como texto para poder mostrar la oferta sin más consultas.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.database import Base
from app.backend.domain.enums import EstadoOferta

if TYPE_CHECKING:
    from app.backend.models.lista_espera import ListaEsperaORM


class OfertaCupoORM(Base):
    __tablename__ = "ofertas_cupo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )
    lista_id: Mapped[int] = mapped_column(
        ForeignKey("listas_espera.id"), nullable=False
    )
    medico_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )

    # Datos de la hora ofrecida (se guardan planos para mostrarla y reservarla).
    medico_nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    especialidad: Mapped[str] = mapped_column(String(120), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    estado: Mapped[EstadoOferta] = mapped_column(
        SQLEnum(EstadoOferta), default=EstadoOferta.PENDIENTE, nullable=False
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    # Solo lectura hacia la lista (para saber de qué cola salió la oferta).
    lista: Mapped["ListaEsperaORM"] = relationship()

    def __repr__(self) -> str:
        return (
            f"OfertaCupoORM(id={self.id}, paciente={self.paciente_id}, "
            f"estado={self.estado.value})"
        )
