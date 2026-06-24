"""Dashboard operacional: citas del día, métricas y lista de espera."""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import EstadoCita, RolUsuario
from app.backend.models.lista_espera import InscripcionEsperaORM
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.citas import RepositorioCitas

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", include_in_schema=False)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)

    if usuario.rol == RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)

    hoy = date.today()
    repo = RepositorioCitas(db)

    if usuario.rol == RolUsuario.MEDICO:
        citas_hoy = repo.listar_del_dia_de_medico(usuario.run_usuario, hoy)
    else:
        citas_hoy = repo.listar_del_dia(hoy)

    pendientes  = sum(1 for c in citas_hoy if c.estado == EstadoCita.PENDIENTE)
    confirmadas = sum(1 for c in citas_hoy if c.estado == EstadoCita.CONFIRMADA)
    canceladas  = sum(1 for c in citas_hoy if c.estado == EstadoCita.CANCELADA)

    total_espera = db.scalar(
        select(func.count()).select_from(InscripcionEsperaORM)
    ) or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "hoy": hoy.strftime("%d/%m/%Y"),
            "citas_hoy": citas_hoy,
            "total_citas": len(citas_hoy),
            "pendientes": pendientes,
            "confirmadas": confirmadas,
            "canceladas": canceladas,
            "total_espera": total_espera,
        },
    )
