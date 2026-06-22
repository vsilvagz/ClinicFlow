"""Páginas web de gestión de especialidades.

Primera funcionalidad usable de extremo a extremo: un formulario crea una
especialidad y una tabla lista las que ya existen. Todo es server-side (Jinja2,
sin JavaScript) y usa el patrón Post/Redirect/Get: tras un POST se redirige a la
página con un mensaje en la query, para que recargar no reenvíe el formulario.
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
from app.backend.schemas.especialidades import EspecialidadCrear
from app.backend.services.especialidades_service import (
    EspecialidadYaExiste,
    crear_especialidad,
    listar_especialidades,
)

router = APIRouter(tags=["especialidades"])


def _no_es_admin(usuario: UsuarioORM | None) -> bool:
    """True si no hay sesión o el usuario no es administrador."""
    return usuario is None or usuario.rol != RolUsuario.ADMINISTRADOR


@router.get("/especialidades", include_in_schema=False)
def pagina_especialidades(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
    creada: str | None = None,
    error: str | None = None,
):
    """Renderiza el formulario y la lista de especialidades registradas."""
    if _no_es_admin(usuario):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        "especialidades.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "especialidades": listar_especialidades(db),
            "creada": creada,
            "error": error,
        },
    )


@router.post("/especialidades", include_in_schema=False)
def crear_especialidad_web(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    """Crea una especialidad desde el formulario y vuelve a la página."""
    if _no_es_admin(usuario):
        return RedirectResponse("/login", status_code=303)
    try:
        datos = EspecialidadCrear(nombre=nombre.strip(), descripcion=descripcion.strip())
    except ValidationError:
        return RedirectResponse("/especialidades?error=invalido", status_code=303)

    try:
        crear_especialidad(db, datos)
    except EspecialidadYaExiste:
        return RedirectResponse("/especialidades?error=existe", status_code=303)

    return RedirectResponse("/especialidades?creada=1", status_code=303)
