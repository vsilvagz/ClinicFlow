"""Página web de reserva de horas médicas.

Flujo completo, server-side (Jinja2, sin JavaScript), centrado en el paciente:

1. El paciente ingresa su RUT.
   - Si está registrado, se le saluda y continúa.
   - Si no, se le pide nombre, correo y teléfono y se registra.
2. Ya identificado, elige un médico y una fecha → se muestran las horas libres.
3. Elige una hora → se crea la cita y se vuelve con un mensaje de confirmación.

Se usa el patrón Post/Redirect/Get: tras cada POST se redirige con el estado en
la query, para que recargar no reenvíe el formulario. La lógica de negocio
(disponibilidad, conflictos, fecha pasada) vive en los servicios y el dominio;
aquí solo se adapta al canal web.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.backend.api.templates import templates
from app.backend.core.config import settings
from app.backend.core.database import get_db
from app.backend.domain.errores import (
    CitaEnPasadoError,
    ConflictoDeAgenda,
    MedicoNoEncontrado,
    PacienteNoEncontrado,
)
from app.backend.schemas.citas import CitaCrear
from app.backend.schemas.usuarios import PacienteCrear
from app.backend.services.agendas_service import slots_disponibles_de_medico
from app.backend.services.citas_service import crear_cita
from app.backend.services.usuarios_service import (
    UsuarioYaExiste,
    crear_paciente,
    listar_medicos,
    obtener_paciente,
)

router = APIRouter(tags=["citas"])


def _parsear_fecha(valor: str | None) -> date:
    """Convierte el texto de la query a fecha; si falta o es inválido, usa hoy."""
    if valor:
        try:
            return date.fromisoformat(valor)
        except ValueError:
            pass
    return date.today()


def _parsear_run(valor: str | None) -> int | None:
    """Normaliza un RUT escrito por el usuario a un entero (sin dígito verificador).

    Acepta formas como "12.345.678-9" o "12345678": descarta puntos, espacios y
    el dígito verificador tras el guion. Devuelve None si no queda un número.
    """
    if not valor:
        return None
    limpio = valor.strip().split("-")[0].replace(".", "").replace(" ", "")
    return int(limpio) if limpio.isdigit() else None


@router.get("/reservar", include_in_schema=False)
def pagina_reservar(
    request: Request,
    db: Session = Depends(get_db),
    paciente_run: int | None = None,
    registrar: int | None = None,
    medico_run: int | None = None,
    fecha: str | None = None,
    creada: str | None = None,
    error: str | None = None,
):
    """Renderiza la página de reserva en el estado que corresponda según la query."""
    paciente = obtener_paciente(db, paciente_run) if paciente_run else None
    fecha_sel = _parsear_fecha(fecha)
    slots = (
        slots_disponibles_de_medico(db, medico_run, fecha_sel)
        if paciente and medico_run is not None
        else []
    )
    return templates.TemplateResponse(
        "reservar.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "paciente": paciente,
            "registrar": registrar,
            "medicos": listar_medicos(db),
            "medico_run": medico_run,
            "fecha": fecha_sel.isoformat(),
            "slots": slots,
            "creada": creada,
            "error": error,
        },
    )


@router.post("/reservar/identificar", include_in_schema=False)
def identificar_paciente(
    run: str = Form(...),
    db: Session = Depends(get_db),
):
    """Busca al paciente por RUT; si existe continúa, si no, pide registrarlo."""
    run_num = _parsear_run(run)
    if run_num is None:
        return RedirectResponse("/reservar?error=run", status_code=303)

    if obtener_paciente(db, run_num) is not None:
        return RedirectResponse(f"/reservar?paciente_run={run_num}", status_code=303)
    return RedirectResponse(f"/reservar?registrar={run_num}", status_code=303)


@router.post("/reservar/registrar", include_in_schema=False)
def registrar_paciente(
    run: int = Form(...),
    nombre: str = Form(...),
    correo: str = Form(...),
    telefono: str = Form(...),
    db: Session = Depends(get_db),
):
    """Registra un paciente nuevo y lo deja identificado para reservar."""
    telefono_num = _parsear_run(telefono)  # mismo saneo de dígitos que el RUT.
    try:
        datos = PacienteCrear(
            run_usuario=run,
            nombre=nombre.strip(),
            correo=correo.strip(),
            telefono=telefono_num or 0,
        )
    except ValidationError:
        return RedirectResponse(f"/reservar?registrar={run}&error=invalido", status_code=303)

    try:
        crear_paciente(db, datos)
    except UsuarioYaExiste:
        # El RUN ya está tomado por otro tipo de usuario (médico, recepcionista…).
        return RedirectResponse(f"/reservar?registrar={run}&error=ocupado", status_code=303)

    return RedirectResponse(f"/reservar?paciente_run={run}", status_code=303)


@router.post("/reservar", include_in_schema=False)
def reservar_web(
    paciente_run: int = Form(...),
    medico_run: int = Form(...),
    inicio: str = Form(...),
    motivo: str = Form(""),
    db: Session = Depends(get_db),
):
    """Crea la cita para el slot elegido y vuelve a la página de reserva."""
    try:
        inicio_dt = datetime.fromisoformat(inicio)
    except ValueError:
        return RedirectResponse(f"/reservar?paciente_run={paciente_run}&error=invalido", status_code=303)

    fecha_q = inicio_dt.date().isoformat()
    base = f"/reservar?paciente_run={paciente_run}&medico_run={medico_run}&fecha={fecha_q}"

    # Revalidar disponibilidad contra la agenda: el slot pudo ocuparse entre que
    # se mostró la página y se envió el formulario.
    if inicio_dt not in slots_disponibles_de_medico(db, medico_run, inicio_dt.date()):
        return RedirectResponse(f"{base}&error=nodisponible", status_code=303)

    datos = CitaCrear(
        paciente_id=paciente_run,
        medico_id=medico_run,
        inicio=inicio_dt,
        motivo=motivo.strip(),
    )
    try:
        crear_cita(db, datos)
    except (PacienteNoEncontrado, MedicoNoEncontrado):
        return RedirectResponse(f"{base}&error=usuario", status_code=303)
    except (ConflictoDeAgenda, CitaEnPasadoError):
        return RedirectResponse(f"{base}&error=nodisponible", status_code=303)

    return RedirectResponse(f"{base}&creada=1", status_code=303)
