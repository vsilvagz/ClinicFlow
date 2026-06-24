"""Gestión de clínicas (sucursales) para el administrador.

CRUD de clínicas: crear, listar, editar y eliminar. Al eliminar una clínica sus
recepcionistas quedan desactivadas y desligadas de ella.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import UsuarioORM
from app.backend.schemas.clinica import ClinicaCrear
from app.backend.services.clinica_service import (
    ClinicaNoEncontrada,
    ClinicaYaExiste,
    crear_clinica,
    editar_clinica,
    eliminar_clinica,
    listar_clinicas,
)

router = APIRouter(tags=["clinicas"])


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.ADMINISTRADOR:
        return RedirectResponse("/portal", status_code=303)
    return None


@router.get("/clinicas", include_in_schema=False)
def clinicas_page(
    request: Request,
    ok: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    return templates.TemplateResponse(
        "clinicas.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "clinicas": listar_clinicas(db),
            "ok": ok,
            "error": error,
        },
    )


@router.post("/clinicas/nueva", include_in_schema=False)
def crear_clinica_web(
    rut_empresa: str = Form(...),
    nombre: str = Form(...),
    direccion: str = Form(default=""),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        datos = ClinicaCrear(
            rut_empresa=rut_empresa.strip(),
            nombre=nombre.strip(),
            direccion=direccion.strip() or "Dirección no especificada",
        )
        crear_clinica(db, datos)
    except ClinicaYaExiste:
        return RedirectResponse("/clinicas?error=rut_ocupado", status_code=303)
    except ValidationError:
        return RedirectResponse("/clinicas?error=invalido", status_code=303)
    return RedirectResponse("/clinicas?ok=creada", status_code=303)


@router.post("/clinicas/editar", include_in_schema=False)
def editar_clinica_web(
    rut_empresa: str = Form(...),
    nombre: str = Form(...),
    direccion: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        editar_clinica(db, usuario, rut_empresa, nombre=nombre.strip(), direccion=direccion.strip())
    except ClinicaNoEncontrada:
        return RedirectResponse("/clinicas?error=no_encontrada", status_code=303)
    except ValueError:
        return RedirectResponse("/clinicas?error=invalido", status_code=303)
    return RedirectResponse("/clinicas?ok=editada", status_code=303)


@router.post("/clinicas/eliminar", include_in_schema=False)
def eliminar_clinica_web(
    rut_empresa: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        eliminar_clinica(db, usuario, rut_empresa)
    except ClinicaNoEncontrada:
        return RedirectResponse("/clinicas?error=no_encontrada", status_code=303)
    return RedirectResponse("/clinicas?ok=eliminada", status_code=303)
