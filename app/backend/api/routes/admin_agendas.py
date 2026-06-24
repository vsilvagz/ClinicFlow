"""Gestión de agendas médicas para el administrador.

El administrador puede configurar la agenda de cualquier médico: definir sus
horarios de atención, bloquear intervalos y suspender períodos. Reutiliza los
mismos servicios de agenda que usa el médico sobre la suya, resolviendo la
agenda a partir del médico elegido.
"""

from datetime import datetime, time

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import MedicoORM, UsuarioORM
from app.backend.repositories.agendas import RepositorioAgendas
from app.backend.schemas.agendas import (
    AgendaCrear,
    BloqueHorarioCrear,
    BloqueoCrear,
    SuspensionCrear,
)
from app.backend.services.agendas_service import (
    agregar_horario,
    bloquear_horario,
    crear_agenda,
    suspender_agenda,
)
from app.backend.services.usuarios_service import listar_medicos

router = APIRouter(tags=["admin-agendas"])

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.ADMINISTRADOR:
        return RedirectResponse("/portal", status_code=303)
    return None


def _agenda_de(db: Session, medico_run: int):
    return RepositorioAgendas(db).obtener_por_medico(medico_run)


@router.get("/admin/agendas", include_in_schema=False)
def admin_agendas(
    request: Request,
    medico_run: int | None = None,
    ok: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    medicos = listar_medicos(db)
    medico = db.get(MedicoORM, medico_run) if medico_run else None
    agenda = _agenda_de(db, medico_run) if medico else None
    horarios = sorted(agenda.horarios, key=lambda h: (h.dia_semana, h.hora_inicio)) if agenda else []
    bloqueos = sorted(agenda.bloqueos, key=lambda b: b.inicio) if agenda else []
    suspensiones = sorted(agenda.suspensiones, key=lambda s: s.inicio) if agenda else []

    return templates.TemplateResponse(
        "admin_agendas.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "medicos": medicos,
            "medico": medico,
            "agenda": agenda,
            "horarios": horarios,
            "bloqueos": bloqueos,
            "suspensiones": suspensiones,
            "dias_semana": DIAS_SEMANA,
            "ok": ok,
            "error": error,
        },
    )


def _volver(medico_run: int, sufijo: str) -> RedirectResponse:
    return RedirectResponse(f"/admin/agendas?medico_run={medico_run}&{sufijo}", status_code=303)


@router.post("/admin/agendas/horario", include_in_schema=False)
def agregar_horario_web(
    medico_run: int = Form(...),
    dia_semana: int = Form(...),
    hora_inicio: str = Form(...),
    hora_fin: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    try:
        # Si el médico aún no tiene agenda, se crea al definir su primer horario.
        agenda = _agenda_de(db, medico_run)
        if agenda is None:
            agenda = crear_agenda(db, AgendaCrear(medico_run=medico_run))
        agregar_horario(
            db,
            agenda.id,
            BloqueHorarioCrear(
                dia_semana=dia_semana,
                hora_inicio=time.fromisoformat(hora_inicio),
                hora_fin=time.fromisoformat(hora_fin),
            ),
        )
    except Exception:
        return _volver(medico_run, "error=invalido")
    return _volver(medico_run, "ok=horario")


@router.post("/admin/agendas/bloquear", include_in_schema=False)
def bloquear_web(
    medico_run: int = Form(...),
    inicio: str = Form(...),
    fin: str = Form(...),
    motivo: str = Form(default=""),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    agenda = _agenda_de(db, medico_run)
    if agenda is None:
        return _volver(medico_run, "error=sin_agenda")
    try:
        bloquear_horario(
            db,
            agenda.id,
            BloqueoCrear(
                inicio=datetime.fromisoformat(inicio),
                fin=datetime.fromisoformat(fin),
                motivo=motivo.strip(),
            ),
        )
    except Exception:
        return _volver(medico_run, "error=invalido")
    return _volver(medico_run, "ok=bloqueado")


@router.post("/admin/agendas/suspender", include_in_schema=False)
def suspender_web(
    medico_run: int = Form(...),
    inicio: str = Form(...),
    fin: str = Form(...),
    motivo: str = Form(default=""),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    agenda = _agenda_de(db, medico_run)
    if agenda is None:
        return _volver(medico_run, "error=sin_agenda")
    try:
        suspender_agenda(
            db,
            agenda.id,
            SuspensionCrear(
                inicio=datetime.fromisoformat(inicio),
                fin=datetime.fromisoformat(fin),
                motivo=motivo.strip(),
            ),
        )
    except Exception:
        return _volver(medico_run, "error=invalido")
    return _volver(medico_run, "ok=suspendido")
