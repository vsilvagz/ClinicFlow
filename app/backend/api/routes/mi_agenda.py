"""Página de gestión de agenda propia para médicos (bloquear y suspender)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.agendas import RepositorioAgendas
from app.backend.schemas.agendas import BloqueoCrear, SuspensionCrear
from app.backend.services.agendas_service import bloquear_horario, suspender_agenda

router = APIRouter(tags=["mi-agenda"])


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.MEDICO:
        return RedirectResponse("/portal", status_code=303)
    return None


@router.get("/mi-agenda", include_in_schema=False)
def mi_agenda(
    request: Request,
    ok: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    agenda = RepositorioAgendas(db).obtener_por_medico(usuario.run_usuario)
    bloqueos = sorted(agenda.bloqueos, key=lambda b: b.inicio) if agenda else []
    suspensiones = sorted(agenda.suspensiones, key=lambda s: s.inicio) if agenda else []

    return templates.TemplateResponse(
        "mi_agenda.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "agenda": agenda,
            "bloqueos": bloqueos,
            "suspensiones": suspensiones,
            "ok": ok,
            "error": error,
        },
    )


@router.post("/mi-agenda/bloquear", include_in_schema=False)
def crear_bloqueo(
    inicio: str = Form(...),
    fin: str = Form(...),
    motivo: str = Form(default=""),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    agenda = RepositorioAgendas(db).obtener_por_medico(usuario.run_usuario)
    if agenda is None:
        return RedirectResponse("/mi-agenda?error=sin_agenda", status_code=303)

    try:
        datos = BloqueoCrear(
            inicio=datetime.fromisoformat(inicio),
            fin=datetime.fromisoformat(fin),
            motivo=motivo.strip(),
        )
        bloquear_horario(db, agenda.id, datos)
    except Exception:
        return RedirectResponse("/mi-agenda?error=invalido", status_code=303)

    return RedirectResponse("/mi-agenda?ok=bloqueado", status_code=303)


@router.post("/mi-agenda/suspender", include_in_schema=False)
def crear_suspension(
    inicio: str = Form(...),
    fin: str = Form(...),
    motivo: str = Form(default=""),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    agenda = RepositorioAgendas(db).obtener_por_medico(usuario.run_usuario)
    if agenda is None:
        return RedirectResponse("/mi-agenda?error=sin_agenda", status_code=303)

    try:
        datos = SuspensionCrear(
            inicio=datetime.fromisoformat(inicio),
            fin=datetime.fromisoformat(fin),
            motivo=motivo.strip(),
        )
        suspender_agenda(db, agenda.id, datos)
    except Exception:
        return RedirectResponse("/mi-agenda?error=invalido", status_code=303)

    return RedirectResponse("/mi-agenda?ok=suspendido", status_code=303)
