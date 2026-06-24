"""Página de gestión de citas para recepcionistas y administradores."""

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.citas import RepositorioCitas
from app.backend.schemas.citas import CitaReagendar
from app.backend.services.agendas_service import slots_disponibles_de_medico
from app.backend.services.citas_service import (
    cancelar_cita,
    confirmar_cita,
    marcar_no_asistio,
    reagendar_cita,
)

router = APIRouter(tags=["gestion-citas"])

_ROLES_PERMITIDOS = {RolUsuario.RECEPCIONISTA, RolUsuario.ADMINISTRADOR}


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol not in _ROLES_PERMITIDOS:
        return RedirectResponse("/portal", status_code=303)
    return None


@router.get("/gestion-citas", include_in_schema=False)
def gestion_citas(
    request: Request,
    fecha: str | None = None,
    ok: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    dia = date.fromisoformat(fecha) if fecha else date.today()
    citas = RepositorioCitas(db).listar_del_dia(dia)

    return templates.TemplateResponse(
        "gestion_citas.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "citas": citas,
            "dia": dia,
            "dia_anterior": (dia - timedelta(days=1)).isoformat(),
            "dia_siguiente": (dia + timedelta(days=1)).isoformat(),
            "ok": ok,
        },
    )


@router.post("/gestion-citas/{cita_id}/confirmar", include_in_schema=False)
def confirmar(
    cita_id: UUID,
    fecha: str | None = Form(default=None),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        confirmar_cita(db, cita_id)
    except Exception:
        pass
    q = f"?fecha={fecha}&ok=confirmada" if fecha else "?ok=confirmada"
    return RedirectResponse(f"/gestion-citas{q}", status_code=303)


@router.post("/gestion-citas/{cita_id}/cancelar", include_in_schema=False)
def cancelar(
    cita_id: UUID,
    fecha: str | None = Form(default=None),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        cancelar_cita(db, cita_id)
    except Exception:
        pass
    q = f"?fecha={fecha}&ok=cancelada" if fecha else "?ok=cancelada"
    return RedirectResponse(f"/gestion-citas{q}", status_code=303)


@router.post("/gestion-citas/{cita_id}/no-asistio", include_in_schema=False)
def no_asistio(
    cita_id: UUID,
    fecha: str | None = Form(default=None),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        marcar_no_asistio(db, cita_id)
    except Exception:
        pass
    q = f"?fecha={fecha}&ok=no_asistio" if fecha else "?ok=no_asistio"
    return RedirectResponse(f"/gestion-citas{q}", status_code=303)


@router.get("/gestion-citas/{cita_id}/reagendar", include_in_schema=False)
def reagendar_form(
    cita_id: UUID,
    request: Request,
    fecha: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    cita = RepositorioCitas(db).obtener(cita_id)
    if cita is None:
        return RedirectResponse("/gestion-citas", status_code=303)

    dia = date.fromisoformat(fecha) if fecha else date.today()
    slots = slots_disponibles_de_medico(db, cita.medico_id, dia)

    return templates.TemplateResponse(
        "reagendar.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "cita": cita,
            "dia": dia,
            "dia_anterior": (dia - timedelta(days=1)).isoformat(),
            "dia_siguiente": (dia + timedelta(days=1)).isoformat(),
            "slots": slots,
            "error": error,
            "action_url": f"/gestion-citas/{cita_id}/reagendar",
            "nav_base": f"/gestion-citas/{cita_id}/reagendar",
            "back_url": f"/gestion-citas?fecha={cita.inicio.date().isoformat()}",
        },
    )


@router.post("/gestion-citas/{cita_id}/reagendar", include_in_schema=False)
def reagendar_submit(
    cita_id: UUID,
    nueva_inicio: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        dt = datetime.fromisoformat(nueva_inicio)
        reagendar_cita(db, cita_id, CitaReagendar(nueva_inicio=dt))
    except Exception:
        return RedirectResponse(
            f"/gestion-citas/{cita_id}/reagendar?error=nodisponible", status_code=303
        )
    return RedirectResponse("/gestion-citas?ok=reagendada", status_code=303)
