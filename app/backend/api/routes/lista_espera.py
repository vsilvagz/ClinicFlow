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
from app.backend.models.clinica import ClinicaORM
from app.backend.models.lista_espera import ListaEsperaORM
from app.backend.models.usuarios import RecepcionistaORM, UsuarioORM
from app.backend.repositories.clinica import RepositorioClinicas
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.lista_espera import InscripcionCrear, ListaEsperaCrear
from app.backend.services.lista_espera_service import (
    ColaVacia,
    OfertaYaPendiente,
    SinCupoDisponible,
    inscribir_paciente,
    obtener_o_crear_lista,
    ofrecer_siguiente_cupo,
)

router = APIRouter(tags=["lista-espera"])

_ROLES_PERMITIDOS = {RolUsuario.RECEPCIONISTA, RolUsuario.ADMINISTRADOR}


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol not in _ROLES_PERMITIDOS:
        return RedirectResponse("/portal", status_code=303)
    return None


def _clinica_del_usuario(db: Session, usuario: UsuarioORM) -> ClinicaORM | None:
    """Clínica de contexto: la de la recepcionista, o la primera para el admin."""
    if isinstance(usuario, RecepcionistaORM) and usuario.clinica_rut:
        return db.get(ClinicaORM, usuario.clinica_rut)
    clinicas = RepositorioClinicas(db).listar()
    return clinicas[0] if clinicas else None


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

    # Especialidades ofrecidas por la clínica de contexto (para elegir al inscribir).
    clinica = _clinica_del_usuario(db, usuario)
    especialidades = sorted(
        clinica.especialidades if clinica else [], key=lambda e: e.nombre
    )

    return templates.TemplateResponse(
        "lista_espera.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "listas": listas_con_cola,
            "total_espera": total_espera,
            "pacientes": pacientes,
            "especialidades": especialidades,
            "prioridades": list(PrioridadEspera),
            "ok": ok,
            "error": error,
        },
    )


@router.post("/lista-espera/inscribir", include_in_schema=False)
def inscribir(
    paciente_id: int = Form(...),
    especialidad_id: int = Form(...),
    prioridad: PrioridadEspera = Form(PrioridadEspera.NORMAL),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    clinica = _clinica_del_usuario(db, usuario)
    if clinica is None:
        return RedirectResponse("/lista-espera?error=sin_clinica", status_code=303)

    try:
        # Ubica (o crea) la lista de esa especialidad en la clínica y luego inscribe.
        lista = obtener_o_crear_lista(
            db,
            ListaEsperaCrear(
                especialidad_id=especialidad_id, clinica_rut=clinica.rut_empresa
            ),
        )
        inscribir_paciente(
            db,
            lista.id,
            InscripcionCrear(paciente_id=paciente_id, prioridad=prioridad),
        )
    except PacienteYaEnEspera:
        return RedirectResponse("/lista-espera?error=duplicado", status_code=303)
    except PacienteNoEncontrado:
        return RedirectResponse("/lista-espera?error=paciente", status_code=303)
    except Exception:
        return RedirectResponse("/lista-espera?error=general", status_code=303)

    return RedirectResponse("/lista-espera?ok=inscrito", status_code=303)


@router.post("/lista-espera/{lista_id}/ofrecer", include_in_schema=False)
def ofrecer_cupo(
    lista_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    """Ofrece la hora más próxima al siguiente en espera (no la asigna directo).

    El paciente recibe la oferta en «Mis mensajes» y decide si la confirma, sigue
    esperando o sale de la lista; la cita solo se crea si él la acepta.
    """
    redir = _check(usuario)
    if redir:
        return redir

    try:
        ofrecer_siguiente_cupo(db, lista_id)
    except ColaVacia:
        return RedirectResponse("/lista-espera?error=cola_vacia", status_code=303)
    except OfertaYaPendiente:
        return RedirectResponse("/lista-espera?error=ya_ofrecido", status_code=303)
    except SinCupoDisponible:
        return RedirectResponse("/lista-espera?error=sin_cupo", status_code=303)
    except Exception:
        return RedirectResponse("/lista-espera?error=general", status_code=303)

    return RedirectResponse("/lista-espera?ok=ofrecido", status_code=303)
