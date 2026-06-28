"""Modelo ORM de los turnos de conversación con el asistente.

Cada fila es un mensaje de un diálogo: lo que escribió el paciente o lo que le
respondió el asistente. Guardar la conversación cumple dos propósitos:

- dar contexto al modelo de lenguaje (los turnos previos se reenvían para que
  entienda mensajes que dependen de lo anterior, p. ej. «el lunes a las 10»);
- dejar registro del historial para mostrarlo y auditarlo.

Es una tabla aparte de `mensajes` (que son notificaciones unidireccionales hacia
el paciente); aquí se modela un diálogo de ida y vuelta.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.core.database import Base

# Autor de un turno. Se guardan en español; al hablar con la API del modelo se
# traducen a los roles que ésta espera ("user"/"assistant").
ROL_USUARIO = "usuario"
ROL_ASISTENTE = "asistente"


class ConversacionMensajeORM(Base):
    __tablename__ = "conversacion_mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )
    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        return (
            f"ConversacionMensajeORM(id={self.id}, paciente={self.paciente_id}, "
            f"rol={self.rol!r})"
        )
