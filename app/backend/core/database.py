"""Conexión a la base de datos: motor, sesiones y base declarativa.

Este módulo es la base técnica de toda la persistencia. Aquí se construye:

- el ENGINE: el objeto que sabe hablar con PostgreSQL (abre conexiones reales).
- SessionLocal: una "fábrica" que crea sesiones; cada sesión es una conversación
  con la base de datos (consultas, inserts, commits) que se abre y se cierra.
- Base: la clase declarativa de la que heredarán TODOS los modelos ORM. Reúne
  el "metadata" (el mapa de todas las tablas) que luego usan Alembic y create_all.
- get_db(): la dependencia que FastAPI inyecta en los endpoints para entregar
  una sesión y asegurarse de cerrarla siempre, incluso si ocurre un error.

El resto del sistema NO crea engines ni sesiones por su cuenta: todo pasa por aquí.
"""

# Iterator: tipo de retorno de get_db(), que entrega (yield) una sesión y luego sigue.
from collections.abc import Iterator

# create_engine: construye el motor de conexión a la base de datos.
from sqlalchemy import create_engine

# DeclarativeBase: clase base moderna (SQLAlchemy 2.0) para definir modelos ORM.
# Session: el tipo de una sesión; sessionmaker: la fábrica que las produce.
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Importamos la configuración ya cargada (lee DATABASE_URL desde el .env).
from app.backend.core.config import settings


# ──────────────────────────────────────────────────────────────────────────────
# ENGINE: el motor de conexión.
# Se crea UNA sola vez al importar el módulo y se reutiliza en toda la app.
# pool_pre_ping=True hace un "ping" antes de usar cada conexión del pool, para
# evitar errores por conexiones que el servidor cerró por inactividad.
# echo=settings.debug imprime el SQL generado en consola cuando DEBUG=true (útil
# para aprender y depurar; conviene apagarlo en producción).
# ──────────────────────────────────────────────────────────────────────────────

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
)


# ──────────────────────────────────────────────────────────────────────────────
# SessionLocal: fábrica de sesiones.
# Cada vez que llamamos a SessionLocal() obtenemos una sesión nueva.
#   autoflush=False    → no envía cambios a la BD automáticamente antes de cada
#                        consulta; nosotros controlamos cuándo con flush()/commit().
#   autocommit=False   → los cambios no se guardan hasta llamar commit() explícito.
#   bind=engine        → todas las sesiones usan el motor definido arriba.
# ──────────────────────────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# ──────────────────────────────────────────────────────────────────────────────
# Base: clase declarativa de la que heredan TODOS los modelos ORM (paso 3).
# Su atributo .metadata reúne la definición de todas las tablas registradas,
# y es lo que Alembic usará para generar las migraciones.
# ──────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Clase base común para todos los modelos ORM del sistema."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# get_db(): dependencia de FastAPI para inyectar una sesión en los endpoints.
# Se usa así en una ruta:  def endpoint(db: Session = Depends(get_db)): ...
#
# Es un generador: entrega (yield) la sesión al endpoint, y cuando este termina
# —haya error o no— el bloque finally cierra la sesión y libera la conexión.
# Esto evita fugas de conexiones, que son una causa típica de caídas en producción.
# ──────────────────────────────────────────────────────────────────────────────

def get_db() -> Iterator[Session]:
    """Entrega una sesión de base de datos y garantiza cerrarla al finalizar."""
    db = SessionLocal()  # Abre una sesión nueva para esta petición.
    try:
        yield db         # Se la entrega al endpoint para que la use.
    finally:
        db.close()       # Pase lo que pase, cierra la sesión al terminar.
