"""Acciones del paciente sobre las ofertas de cupo liberado.

Cuando se libera una hora, la lista de espera crea una oferta y la muestra en
«Mis mensajes». Desde ahí el paciente decide qué hacer con ella. Estas rutas
reciben esa decisión y delegan en el servicio; toda la lógica (crear la cita,
retirar de la lista, pasar la hora al siguiente) vive en `lista_espera_service`.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.domain.errores import ClinicFlowError
from app.backend.models.usuarios import UsuarioORM
from app.backend.services.lista_espera_service import (
    OfertaNoEncontrada,
    aceptar_oferta,
    salir_de_la_lista,
    seguir_esperando,
)

router = APIRouter(tags=["ofertas"])


def _guardia(usuario: UsuarioORM | None):
    """Solo pacientes autenticados pueden responder ofertas."""
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.PACIENTE:
        return RedirectResponse("/portal", status_code=303)
    return None


@router.post("/ofertas/{oferta_id}/aceptar", include_in_schema=False)
def aceptar(
    oferta_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    """Confirma la hora ofrecida: crea la cita (PENDIENTE) y sale de la lista."""
    redir = _guardia(usuario)
    if redir:
        return redir
    try:
        aceptar_oferta(db, oferta_id, usuario.run_usuario)
    except OfertaNoEncontrada:
        return RedirectResponse("/mis-mensajes", status_code=303)
    except ClinicFlowError:
        # La hora ya no estaba disponible; el paciente quedó notificado.
        return RedirectResponse("/mis-mensajes", status_code=303)
    return RedirectResponse("/mis-citas", status_code=303)


@router.post("/ofertas/{oferta_id}/seguir", include_in_schema=False)
def seguir(
    oferta_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    """Deja pasar la hora pero sigue en la lista de espera."""
    redir = _guardia(usuario)
    if redir:
        return redir
    try:
        seguir_esperando(db, oferta_id, usuario.run_usuario)
    except OfertaNoEncontrada:
        pass
    return RedirectResponse("/mis-mensajes", status_code=303)


@router.post("/ofertas/{oferta_id}/salir", include_in_schema=False)
def salir(
    oferta_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    """Rechaza la hora y se sale de la lista de espera."""
    redir = _guardia(usuario)
    if redir:
        return redir
    try:
        salir_de_la_lista(db, oferta_id, usuario.run_usuario)
    except OfertaNoEncontrada:
        pass
    return RedirectResponse("/mis-mensajes", status_code=303)
