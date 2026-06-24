"""Modelo ORM para mensajes/notificaciones enviados a pacientes."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.database import Base


class MensajeORM(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paciente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.run_usuario"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    paciente: Mapped["UsuarioORM"] = relationship(
        "UsuarioORM", foreign_keys=[paciente_id]
    )

    def __repr__(self) -> str:
        return (
            f"MensajeORM(id={self.id}, paciente={self.paciente_id}, "
            f"tipo={self.tipo!r}, leida={self.leida})"
        )
