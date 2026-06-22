"""Plantillas Jinja2 y rutas de la interfaz web, compartidas por la capa web.

Tanto el punto de entrada (`main.py`) como los routers que renderizan páginas
usan ESTE objeto `templates`, en vez de construir cada uno el suyo. Así la ruta
a la carpeta de plantillas se resuelve en un solo lugar.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

# Este archivo vive en app/backend/api/, y el frontend en app/frontend/:
#   templates.py → api → backend → app → (raíz)/frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# Objeto único de plantillas que renderiza los HTML de app/frontend/templates.
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
