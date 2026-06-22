"""Punto de entrada de la aplicación FastAPI.

Este módulo arma y expone el objeto `app` que Uvicorn ejecuta. Es el lugar donde
todas las piezas del backend se conectan entre sí:

- Se crea la instancia de FastAPI con los datos de la app (nombre, versión).
- Al arrancar, se crean las tablas de la base de datos a partir de los modelos ORM.
- Se montan los archivos estáticos y las plantillas de la interfaz web.
- Se publica la página de inicio y se incluyen los routers de la API (por ahora,
  el de salud; los demás se irán sumando aquí a medida que se implementen).

La regla de diseño es que este archivo SOLO ensambla: la lógica vive en el
dominio y los servicios, las rutas en sus propios routers. Aquí se conectan.
"""

# asynccontextmanager: construye el manejador de ciclo de vida (lifespan) que
# corre código al iniciar y al apagar la aplicación.
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

# StaticFiles sirve CSS/JS/imágenes; Jinja2Templates renderiza HTML con variables.
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.backend.api.routes import health
from app.backend.core.config import settings
from app.backend.core.database import Base, engine

# Importar el paquete de modelos REGISTRA todas las tablas en Base.metadata.
# Sin este import, create_all() no sabría qué tablas crear.
from app.backend import models  # noqa: F401  (import por efecto secundario)


# ──────────────────────────────────────────────────────────────────────────────
# Rutas del frontend: ubicamos las carpetas de plantillas y estáticos de forma
# robusta a partir de este archivo, para que funcione igual en local y en Docker.
#   main.py → backend → app → (raíz)/frontend
# ──────────────────────────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


# ──────────────────────────────────────────────────────────────────────────────
# lifespan: se ejecuta UNA vez al levantar la app y otra al apagarla.
# Al iniciar creamos las tablas que falten (create_all es idempotente: no toca
# las que ya existen). Para producción real se usaría Alembic, pero esto deja el
# sistema ejecutable de inmediato sin pasos manuales.
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
    # (Al apagar no hay recursos extra que liberar por ahora.)


# ──────────────────────────────────────────────────────────────────────────────
# Instancia principal de la aplicación.
# title/version/docs alimentan la documentación interactiva en /docs.
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    summary="Plataforma de gestión clínica conversacional",
    lifespan=lifespan,
)

# Servimos los archivos estáticos (hoja de estilos) bajo /static.
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="static",
)

# Montamos los routers de la API. Cada módulo nuevo (citas, usuarios, …) se
# incluye aquí cuando esté listo.
app.include_router(health.router)


# ──────────────────────────────────────────────────────────────────────────────
# GET / → página de inicio de la interfaz web.
# Renderiza la plantilla index.html pasándole el nombre de la app. Es la puerta
# de entrada visual; la documentación de la API queda en /docs.
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.app_name},
    )
