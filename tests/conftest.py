"""Configuración y fixtures de los tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Importar el paquete de modelos registra todas las tablas en Base.metadata,
# que es lo que create_all() necesita para construir el esquema.
import app.backend.models  # noqa: F401
from app.backend.core.database import Base


@pytest.fixture
def db() -> Session:
    """Sesión sobre una base SQLite en memoria, nueva y aislada por test.

    StaticPool mantiene UNA sola conexión compartida: así la base en memoria
    (que vive ligada a su conexión) y sus tablas son visibles también desde
    otros hilos, como el que usa TestClient para atender las peticiones.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    try:
        yield sesion
    finally:
        sesion.close()
        engine.dispose()
