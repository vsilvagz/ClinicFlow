"""Dependencias de la capa de presentación (sesión del usuario).

La sesión se mantiene con un JWT guardado en una cookie HttpOnly: el navegador la
envía sola en cada request y JavaScript no puede leerla. Estas dependencias leen
esa cookie y resuelven el usuario actual, para que las rutas no repitan esa lógica.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.backend.core.database import get_db
from app.backend.core.security import leer_token
from app.backend.models.usuarios import UsuarioORM

# Nombre de la cookie donde vive el token de sesión.
COOKIE_SESION = "session"


def usuario_actual(
    request: Request, db: Session = Depends(get_db)
) -> UsuarioORM | None:
    """Devuelve el usuario autenticado según la cookie de sesión, o None."""
    token = request.cookies.get(COOKIE_SESION)
    run = leer_token(token) if token else None
    if run is None:
        return None
    try:
        return db.get(UsuarioORM, int(run))
    except (TypeError, ValueError):
        return None
