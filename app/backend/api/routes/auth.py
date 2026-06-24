"""Páginas web de autenticación: inicio y cierre de sesión.

El inicio de sesión es por RUT + contraseña. Si las credenciales son válidas se
emite un JWT y se guarda en una cookie HttpOnly; cerrar sesión simplemente borra
esa cookie. El portal es una página protegida de ejemplo que solo se ve con sesión
iniciada.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.backend.api.deps import COOKIE_SESION, usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.core.rut import parsear_run
from app.backend.core.security import crear_token
from app.backend.domain.enums import RolUsuario
from app.backend.models.usuarios import UsuarioORM
from app.backend.services.usuarios_service import autenticar

router = APIRouter(tags=["auth"])


# Tarjetas del portal por rol. Cada rol ve solo las herramientas que le competen
# (p. ej. solo el administrador gestiona especialidades). Una tarjeta sin `href`
# se muestra como "próximamente" porque su página aún no existe.
def _tarjetas_portal(rol: RolUsuario) -> list[dict]:
    reservar = {"titulo": "Reservar hora", "desc": "Agenda una cita por especialidad y médico.", "href": "/reservar"}
    mis_citas_card = {"titulo": "Mis citas", "desc": "Revisa y cancela tus próximas horas.", "href": "/mis-citas"}
    if rol == RolUsuario.ADMINISTRADOR:
        return [
            {"titulo": "Dashboard", "desc": "Citas del día, métricas y lista de espera.", "href": "/dashboard"},
            {"titulo": "Agenda médica", "desc": "Visualiza la agenda de todos los médicos.", "href": "/agenda"},
            {"titulo": "Especialidades", "desc": "Administra el catálogo de especialidades.", "href": "/especialidades"},
            {"titulo": "Lista de espera", "desc": "Supervisa los pacientes en espera.", "href": "/lista-espera"},
        ]
    if rol == RolUsuario.RECEPCIONISTA:
        return [
            {"titulo": "Dashboard", "desc": "Citas del día, métricas y lista de espera.", "href": "/dashboard"},
            {"titulo": "Agenda médica", "desc": "Visualiza la agenda de todos los médicos.", "href": "/agenda"},
            {"titulo": "Gestión de citas", "desc": "Confirma, cancela y reagenda horas.", "href": "/reservar"},
            {"titulo": "Lista de espera", "desc": "Inscribe y asigna cupos a pacientes.", "href": "/lista-espera"},
        ]
    if rol == RolUsuario.MEDICO:
        return [
            {"titulo": "Dashboard", "desc": "Tus citas del día y métricas.", "href": "/dashboard"},
            {"titulo": "Mi agenda", "desc": "Visualiza tus citas del día por fecha.", "href": "/agenda"},
            {"titulo": "Derivaciones", "desc": "Deriva pacientes a otras especialidades.", "href": "/derivaciones"},
        ]
    # Paciente.
    return [reservar, mis_citas_card]


@router.get("/login", include_in_schema=False)
def pagina_login(request: Request, error: str | None = None):
    """Muestra el formulario de inicio de sesión."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "app_name": settings.app_name, "error": error},
    )


@router.post("/login", include_in_schema=False)
def iniciar_sesion(
    run: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Valida las credenciales y, si son correctas, abre la sesión por cookie."""
    run_num = parsear_run(run)
    usuario = autenticar(db, run_num, password) if run_num is not None else None
    if usuario is None:
        return RedirectResponse("/login?error=credenciales", status_code=303)

    respuesta = RedirectResponse("/portal", status_code=303)
    respuesta.set_cookie(
        key=COOKIE_SESION,
        value=crear_token(str(usuario.run_usuario)),
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return respuesta


@router.get("/logout", include_in_schema=False)
def cerrar_sesion():
    """Cierra la sesión borrando la cookie."""
    respuesta = RedirectResponse("/", status_code=303)
    respuesta.delete_cookie(COOKIE_SESION)
    return respuesta


@router.get("/portal", include_in_schema=False)
def portal(request: Request, usuario: UsuarioORM | None = Depends(usuario_actual)):
    """Página protegida: solo accesible con sesión iniciada."""
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        "portal.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "tarjetas": _tarjetas_portal(usuario.rol),
        },
    )
