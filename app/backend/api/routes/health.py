"""Endpoints de salud y diagnóstico.

Sirven para que un operador (o una plataforma de despliegue como Render/Railway)
verifique con una sola petición que la aplicación está viva y que además puede
hablar con la base de datos. Es lo primero que conviene tener funcionando: si
`/health` responde 200, el resto de la API tiene los cimientos en pie.
"""

# APIRouter: agrupa endpoints relacionados para luego montarlos en la app.
# Depends: inyecta dependencias (aquí, la sesión de base de datos).
from fastapi import APIRouter, Depends

# text(): envuelve SQL crudo para ejecutarlo de forma segura con SQLAlchemy 2.0.
from sqlalchemy import text
from sqlalchemy.orm import Session

# get_db entrega una sesión por petición y la cierra al terminar.
from app.backend.core.config import settings
from app.backend.core.database import get_db

# prefix y tags ordenan estos endpoints bajo /health en la documentación /docs.
router = APIRouter(prefix="/health", tags=["health"])


# ──────────────────────────────────────────────────────────────────────────────
# GET /health → ¿está viva la aplicación?
# No toca la base de datos: es un chequeo "liveness" ultra liviano.
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", summary="Estado general de la aplicación")
def health() -> dict[str, str]:
    """Confirma que el servicio responde y devuelve datos básicos de la app."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


# ──────────────────────────────────────────────────────────────────────────────
# GET /health/db → ¿está disponible la base de datos?
# Ejecuta un SELECT 1 trivial: si la conexión funciona, devuelve "ok".
# Es el chequeo "readiness": la app puede estar viva pero sin BD todavía no
# debería recibir tráfico real.
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/db", summary="Conectividad con la base de datos")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Verifica la conexión a la base de datos con una consulta mínima."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
