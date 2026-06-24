"""Página de derivaciones para médicos."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.derivacion import DerivacionORM
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.derivaciones import RepositorioDerivaciones
from app.backend.schemas.derivaciones import DerivacionCrear
from app.backend.services.derivaciones_service import emitir_derivacion

router = APIRouter(tags=["derivaciones"])

_ROLES_MEDICO_ADMIN = {RolUsuario.MEDICO, RolUsuario.ADMINISTRADOR}


@router.get("/derivaciones", include_in_schema=False)
def derivaciones_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol not in _ROLES_MEDICO_ADMIN:
        return RedirectResponse("/portal", status_code=303)

    if usuario.rol == RolUsuario.MEDICO:
        derivaciones_lista = list(db.scalars(
            select(DerivacionORM)
            .where(DerivacionORM.medico_origen_id == usuario.run_usuario)
            .order_by(DerivacionORM.creada_en.desc())
        ))
    else:
        derivaciones_lista = list(db.scalars(
            select(DerivacionORM).order_by(DerivacionORM.creada_en.desc())
        ))

    especialidades = list(db.scalars(select(EspecialidadORM).order_by(EspecialidadORM.nombre)))

    return templates.TemplateResponse(
        "derivaciones.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "derivaciones": derivaciones_lista,
            "especialidades": especialidades,
        },
    )


@router.post("/derivaciones/nueva", include_in_schema=False)
def nueva_derivacion(
    paciente_id: int = Form(...),
    especialidad_destino: str = Form(...),
    motivo: str = Form(default=""),
    dias_vigencia: int = Form(default=30),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.MEDICO:
        return RedirectResponse("/portal", status_code=303)

    try:
        datos = DerivacionCrear(
            paciente_id=paciente_id,
            medico_origen_id=usuario.run_usuario,
            especialidad_destino=especialidad_destino,
            motivo=motivo,
            dias_vigencia=dias_vigencia,
        )
        emitir_derivacion(db, datos)
    except Exception:
        pass

    return RedirectResponse("/derivaciones", status_code=303)
