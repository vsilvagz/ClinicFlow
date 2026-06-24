"""Página de lista de espera para recepcionistas y administradores."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.domain.lista_espera import _PESO_PRIORIDAD
from app.backend.models.lista_espera import InscripcionEsperaORM, ListaEsperaORM
from app.backend.models.usuarios import UsuarioORM
from app.backend.services.lista_espera_service import asignar_siguiente_cupo

router = APIRouter(tags=["lista-espera"])

_ROLES_PERMITIDOS = {RolUsuario.RECEPCIONISTA, RolUsuario.ADMINISTRADOR}


@router.get("/lista-espera", include_in_schema=False)
def lista_espera(
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol not in _ROLES_PERMITIDOS:
        return RedirectResponse("/portal", status_code=303)

    listas = list(db.scalars(select(ListaEsperaORM)))

    # Para cada lista, ordenar inscripciones por prioridad y antigüedad
    listas_con_cola = []
    for lista in listas:
        cola = sorted(
            lista.inscripciones,
            key=lambda i: (_PESO_PRIORIDAD[i.prioridad], i.fecha_inscripcion),
        )
        listas_con_cola.append({"lista": lista, "cola": cola})

    total_espera = sum(len(lc["cola"]) for lc in listas_con_cola)

    return templates.TemplateResponse(
        "lista_espera.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "listas": listas_con_cola,
            "total_espera": total_espera,
        },
    )


@router.post("/lista-espera/{lista_id}/asignar", include_in_schema=False)
def asignar_cupo(
    lista_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol not in _ROLES_PERMITIDOS:
        return RedirectResponse("/portal", status_code=303)

    try:
        asignar_siguiente_cupo(db, lista_id)
    except Exception:
        pass

    return RedirectResponse("/lista-espera", status_code=303)
