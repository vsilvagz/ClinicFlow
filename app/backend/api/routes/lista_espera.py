"""Página de lista de espera para recepcionistas y administradores."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import PrioridadEspera, RolUsuario
from app.backend.domain.errores import PacienteNoEncontrado, PacienteYaEnEspera
from app.backend.domain.lista_espera import _PESO_PRIORIDAD
from app.backend.models.lista_espera import ListaEsperaORM
from app.backend.models.usuarios import UsuarioORM
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.lista_espera import InscripcionCrear
from app.backend.services.lista_espera_service import (
    ColaVacia,
    SinCupoDisponible,
    asignar_siguiente_cupo,
    inscribir_paciente,
)

router = APIRouter(tags=["lista-espera"])

_ROLES_PERMITIDOS = {RolUsuario.RECEPCIONISTA, RolUsuario.ADMINISTRADOR}


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol not in _ROLES_PERMITIDOS:
        return RedirectResponse("/portal", status_code=303)
    return None


@router.get("/lista-espera", include_in_schema=False)
def lista_espera(
    request: Request,
    ok: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

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
    pacientes = RepositorioUsuarios(db).listar_pacientes()

    return templates.TemplateResponse(
        "lista_espera.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "listas": listas_con_cola,
            "total_espera": total_espera,
            "pacientes": pacientes,
            "prioridades": list(PrioridadEspera),
            "ok": ok,
            "error": error,
        },
    )


@router.post("/lista-espera/{lista_id}/inscribir", include_in_schema=False)
def inscribir(
    lista_id: int,
    paciente_id: int = Form(...),
    prioridad: PrioridadEspera = Form(PrioridadEspera.NORMAL),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    try:
        inscribir_paciente(
            db,
            lista_id,
            InscripcionCrear(paciente_id=paciente_id, prioridad=prioridad),
        )
    except PacienteYaEnEspera:
        return RedirectResponse("/lista-espera?error=duplicado", status_code=303)
    except PacienteNoEncontrado:
        return RedirectResponse("/lista-espera?error=paciente", status_code=303)
    except Exception:
        return RedirectResponse("/lista-espera?error=general", status_code=303)

    return RedirectResponse("/lista-espera?ok=inscrito", status_code=303)


@router.post("/lista-espera/{lista_id}/asignar", include_in_schema=False)
def asignar_cupo(
    lista_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    try:
        asignar_siguiente_cupo(db, lista_id)
    except ColaVacia:
        return RedirectResponse("/lista-espera?error=cola_vacia", status_code=303)
    except SinCupoDisponible:
        return RedirectResponse("/lista-espera?error=sin_cupo", status_code=303)
    except Exception:
        return RedirectResponse("/lista-espera?error=general", status_code=303)

    return RedirectResponse("/lista-espera?ok=asignado", status_code=303)
