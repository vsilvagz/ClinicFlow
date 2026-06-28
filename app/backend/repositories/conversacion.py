"""Repositorio de los turnos de conversación con el asistente."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.conversacion import ConversacionMensajeORM
from app.backend.repositories.base import RepositorioBase


class RepositorioConversacion(RepositorioBase[ConversacionMensajeORM]):
    """Acceso a datos de la tabla `conversacion_mensajes`."""

    def __init__(self, db: Session):
        super().__init__(db, ConversacionMensajeORM)

    def agregar_turno(self, paciente_id: int, rol: str, contenido: str) -> ConversacionMensajeORM:
        """Registra un turno (del paciente o del asistente) y lo persiste."""
        turno = ConversacionMensajeORM(
            paciente_id=paciente_id, rol=rol, contenido=contenido
        )
        self.db.add(turno)
        self.db.commit()
        self.db.refresh(turno)
        return turno

    def ultimos_de_paciente(
        self, paciente_id: int, limite: int = 10
    ) -> list[ConversacionMensajeORM]:
        """Devuelve los últimos `limite` turnos del paciente, en orden cronológico.

        Se consultan los más recientes (orden descendente) y se invierten, para
        entregar la ventana de contexto del más antiguo al más nuevo.
        """
        recientes = list(
            self.db.scalars(
                select(ConversacionMensajeORM)
                .where(ConversacionMensajeORM.paciente_id == paciente_id)
                .order_by(ConversacionMensajeORM.id.desc())
                .limit(limite)
            )
        )
        return list(reversed(recientes))
