"""Página de citas del paciente: ver historial, cancelar y reagendar."""

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
from app.backend.domain.errores import TransicionEstadoInvalida
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.citas import RepositorioCitas
from app.backend.schemas.citas import CitaReagendar
from app.backend.services.agendas_service import slots_disponibles_de_medico
from app.backend.services.citas_service import cancelar_cita, reagendar_cita

router = APIRouter(tags=["mis-citas"])


@router.get("/mis-citas", include_in_schema=False)
def mis_citas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    citas = RepositorioCitas(db).listar_de_paciente(usuario.run_usuario)
    citas_ordenadas = sorted(citas, key=lambda c: c.inicio, reverse=True)

    return templates.TemplateResponse(
        "mis_citas.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "citas": citas_ordenadas,
        },
    )


@router.post("/mis-citas/{cita_id}/cancelar", include_in_schema=False)
def cancelar_mi_cita(
    cita_id: UUID,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    try:
        cancelar_cita(db, cita_id)
    except (TransicionEstadoInvalida, Exception):
        pass

    return RedirectResponse("/mis-citas", status_code=303)


@router.get("/mis-citas/{cita_id}/reagendar", include_in_schema=False)
def reagendar_form(
    cita_id: UUID,
    request: Request,
    fecha: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    cita = RepositorioCitas(db).obtener(cita_id)
    if cita is None or cita.paciente_id != usuario.run_usuario:
        return RedirectResponse("/mis-citas", status_code=303)

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
            "action_url": f"/mis-citas/{cita_id}/reagendar",
            "nav_base": f"/mis-citas/{cita_id}/reagendar",
            "back_url": "/mis-citas",
        },
    )


@router.post("/mis-citas/{cita_id}/reagendar", include_in_schema=False)
def reagendar_submit(
    cita_id: UUID,
    nueva_inicio: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    cita = RepositorioCitas(db).obtener(cita_id)
    if cita is None or cita.paciente_id != usuario.run_usuario:
        return RedirectResponse("/mis-citas", status_code=303)

    try:
        dt = datetime.fromisoformat(nueva_inicio)
        reagendar_cita(db, cita_id, CitaReagendar(nueva_inicio=dt))
    except Exception:
        return RedirectResponse(
            f"/mis-citas/{cita_id}/reagendar?error=nodisponible", status_code=303
        )
    return RedirectResponse("/mis-citas", status_code=303)
