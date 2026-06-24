"""Página de gestión de usuarios para administradores."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.api.deps import usuario_actual
from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.enums import RolUsuario
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import (
    AdministradorORM,
    MedicoORM,
    PacienteORM,
    RecepcionistaORM,
    UsuarioORM,
)
from app.backend.schemas.usuarios import (
    AdministradorCrear,
    MedicoCrear,
    PacienteCrear,
    RecepcionistaCrear,
)
from app.backend.services.usuarios_service import (
    EspecialidadNoEncontrada,
    UltimoAdministrador,
    UsuarioNoEncontrado,
    UsuarioYaExiste,
    cambiar_estado_usuario,
    cambiar_rol,
    crear_administrador,
    crear_medico,
    crear_paciente,
    crear_recepcionista,
    editar_usuario,
    resetear_password,
)

router = APIRouter(tags=["usuarios"])


def _check(usuario: UsuarioORM | None):
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if usuario.rol != RolUsuario.ADMINISTRADOR:
        return RedirectResponse("/portal", status_code=303)
    return None


@router.get("/usuarios", include_in_schema=False)
def usuarios_page(
    request: Request,
    ok: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    medicos = list(db.scalars(select(MedicoORM).order_by(MedicoORM.nombre)))
    recepcionistas = list(db.scalars(select(RecepcionistaORM).order_by(RecepcionistaORM.nombre)))
    pacientes = list(db.scalars(select(PacienteORM).order_by(PacienteORM.nombre)))
    admins = list(db.scalars(select(AdministradorORM).order_by(AdministradorORM.nombre)))
    especialidades = list(db.scalars(select(EspecialidadORM).order_by(EspecialidadORM.nombre)))

    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "usuario": usuario,
            "medicos": medicos,
            "recepcionistas": recepcionistas,
            "pacientes": pacientes,
            "admins": admins,
            "especialidades": especialidades,
            "ok": ok,
            "error": error,
        },
    )


@router.post("/usuarios/nuevo", include_in_schema=False)
def crear_usuario(
    rol: str = Form(...),
    run_usuario: int = Form(...),
    nombre: str = Form(...),
    correo: str = Form(...),
    telefono: int = Form(...),
    password: str | None = Form(default=None),
    especialidad_id: int | None = Form(default=None),
    clinica_rut: str | None = Form(default=None),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir

    campos_base = dict(
        run_usuario=run_usuario,
        nombre=nombre.strip(),
        correo=correo.strip(),
        telefono=telefono,
        password=password if password else None,
    )

    try:
        match rol:
            case "PACIENTE":
                crear_paciente(db, PacienteCrear(**campos_base))
            case "MEDICO":
                if not especialidad_id:
                    return RedirectResponse("/usuarios?error=especialidad", status_code=303)
                crear_medico(db, MedicoCrear(**campos_base, especialidad_id=especialidad_id))
            case "RECEPCIONISTA":
                rut = (clinica_rut or "").strip()
                if not rut:
                    return RedirectResponse("/usuarios?error=clinica", status_code=303)
                crear_recepcionista(db, RecepcionistaCrear(**campos_base, clinica_rut=rut))
            case "ADMINISTRADOR":
                crear_administrador(db, AdministradorCrear(**campos_base))
            case _:
                return RedirectResponse("/usuarios?error=rol", status_code=303)
    except UsuarioYaExiste:
        return RedirectResponse("/usuarios?error=run_ocupado", status_code=303)
    except Exception:
        return RedirectResponse("/usuarios?error=invalido", status_code=303)

    return RedirectResponse("/usuarios?ok=creado", status_code=303)


@router.post("/usuarios/{run}/editar", include_in_schema=False)
def editar_usuario_web(
    run: int,
    nombre: str = Form(...),
    correo: str = Form(...),
    telefono: int = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        editar_usuario(db, usuario, run, nombre=nombre.strip(), correo=correo.strip(), telefono=telefono)
    except UsuarioNoEncontrado:
        return RedirectResponse("/usuarios?error=no_encontrado", status_code=303)
    except Exception:
        return RedirectResponse("/usuarios?error=invalido", status_code=303)
    return RedirectResponse("/usuarios?ok=editado", status_code=303)


@router.post("/usuarios/{run}/estado", include_in_schema=False)
def cambiar_estado_web(
    run: int,
    activo: int = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        cambiar_estado_usuario(db, usuario, run, bool(activo))
    except UsuarioNoEncontrado:
        return RedirectResponse("/usuarios?error=no_encontrado", status_code=303)
    except UltimoAdministrador:
        return RedirectResponse("/usuarios?error=ultimo_admin", status_code=303)
    except ValueError:
        return RedirectResponse("/usuarios?error=auto_baja", status_code=303)
    return RedirectResponse("/usuarios?ok=estado", status_code=303)


@router.post("/usuarios/{run}/password", include_in_schema=False)
def resetear_password_web(
    run: int,
    password: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        resetear_password(db, run, password)
    except UsuarioNoEncontrado:
        return RedirectResponse("/usuarios?error=no_encontrado", status_code=303)
    except ValueError:
        return RedirectResponse("/usuarios?error=password", status_code=303)
    return RedirectResponse("/usuarios?ok=password", status_code=303)


@router.post("/usuarios/{run}/rol", include_in_schema=False)
def cambiar_rol_web(
    run: int,
    rol: str = Form(...),
    especialidad_id: int | None = Form(default=None),
    clinica_rut: str | None = Form(default=None),
    db: Session = Depends(get_db),
    usuario: UsuarioORM | None = Depends(usuario_actual),
):
    redir = _check(usuario)
    if redir:
        return redir
    try:
        nuevo_rol = RolUsuario[rol]
    except KeyError:
        return RedirectResponse("/usuarios?error=rol", status_code=303)
    try:
        cambiar_rol(db, run, nuevo_rol, especialidad_id=especialidad_id, clinica_rut=clinica_rut)
    except UsuarioNoEncontrado:
        return RedirectResponse("/usuarios?error=no_encontrado", status_code=303)
    except UltimoAdministrador:
        return RedirectResponse("/usuarios?error=ultimo_admin", status_code=303)
    except EspecialidadNoEncontrada:
        return RedirectResponse("/usuarios?error=especialidad", status_code=303)
    except ValueError:
        return RedirectResponse("/usuarios?error=clinica", status_code=303)
    return RedirectResponse("/usuarios?ok=rol", status_code=303)
