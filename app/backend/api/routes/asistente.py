"""Asistente conversacional por web: recibe un mensaje y responde.

Reúne las dos mitades del asistente —interpretar (modelo de lenguaje) y
despachar (servicios de negocio)— detrás de un endpoint HTTP. Como el paciente
ya está autenticado, su RUN se toma de la sesión y no se pide en el mensaje.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.backend.ai.cliente import interpretar
from app.backend.ai.despachador import despachar
from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import UsuarioORM

router = APIRouter(tags=["asistente"])


class MensajeEntrada(BaseModel):
    """Cuerpo de la petición: el texto que escribió el paciente."""

    mensaje: str


@router.get("/asistente", include_in_schema=False)
def pagina_asistente(
    request: Request,
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    """Página de chat con el asistente, solo para pacientes autenticados."""
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)
    return templates.TemplateResponse(
        "asistente.html",
        {"request": request, "app_name": settings.app_name, "usuario": usuario},
    )


@router.post("/asistente/mensaje")
def conversar(
    entrada: MensajeEntrada,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
) -> dict:
    """Interpreta el mensaje del paciente, ejecuta la acción y devuelve la respuesta."""
    if usuario is None or usuario.rol != RolUsuario.PACIENTE:
        raise HTTPException(status_code=401, detail="Sesión de paciente requerida.")

    intencion = interpretar(entrada.mensaje)
    respuesta = despachar(db, usuario.run_usuario, intencion)
    return {"respuesta": respuesta, "accion": intencion.accion.value}
