"""Página de mensajes/notificaciones para el paciente."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.mensajes import MensajeORM
from app.backend.models.usuarios import UsuarioORM

router = APIRouter(tags=["mis-mensajes"])


@router.get("/mis-mensajes", include_in_schema=False)
def mis_mensajes(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    mensajes = list(db.scalars(
        select(MensajeORM)
        .where(MensajeORM.paciente_id == usuario.run_usuario)
        .order_by(MensajeORM.creada_en.desc())
    ))

    # Marcar todos como leídos al visitar la página.
    for m in mensajes:
        if not m.leida:
            m.leida = True
    db.commit()

    return templates.TemplateResponse(
        "mis_mensajes.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "mensajes": mensajes,
        },
    )
