"""Visualización de agendas médicas (enunciado 3.4)."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import MedicoORM, UsuarioORM
from app.backend.repositories.citas import RepositorioCitas
from app.backend.repositories.usuarios import RepositorioUsuarios

router = APIRouter(tags=["agenda"])


@router.get("/agenda", include_in_schema=False)
def agenda_diaria(
    request: Request,
    fecha: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)

    if usuario.rol == RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    try:
        dia = date.fromisoformat(fecha) if fecha else date.today()
    except ValueError:
        dia = date.today()

    repo_citas = RepositorioCitas(db)

    if usuario.rol == RolUsuario.MEDICO:
        medico_orm = db.get(MedicoORM, usuario.run_usuario)
        medicos = [medico_orm] if medico_orm else []
        citas_dia = repo_citas.listar_del_dia_de_medico(usuario.run_usuario, dia)
    else:
        medicos = RepositorioUsuarios(db).listar_medicos()
        citas_dia = repo_citas.listar_del_dia(dia)

    # Agrupar citas por médico
    citas_por_medico: dict[int, list] = {}
    for cita in citas_dia:
        citas_por_medico.setdefault(cita.medico_id, []).append(cita)

    agenda = [
        {
            "medico": m,
            "citas": sorted(citas_por_medico.get(m.run_usuario, []), key=lambda c: c.inicio),
        }
        for m in medicos
    ]

    return templates.TemplateResponse(
        "agenda.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "dia_display": dia.strftime("%d/%m/%Y"),
            "dia_iso": dia.isoformat(),
            "dia_anterior": (dia - timedelta(days=1)).isoformat(),
            "dia_siguiente": (dia + timedelta(days=1)).isoformat(),
            "agenda": agenda,
        },
    )
