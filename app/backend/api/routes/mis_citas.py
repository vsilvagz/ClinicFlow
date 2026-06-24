"""Página de citas del paciente: ver historial y cancelar."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
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
from app.backend.services.citas_service import cancelar_cita

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
