"""Configuración de la aplicación a partir de variables de entorno.

Toda la configuración del sistema (URL de la base de datos, claves secretas,
tokens de Telegram, etc.) se centraliza aquí. En vez de leer variables de
entorno sueltas por todo el código, las cargamos UNA vez en la clase Settings
y el resto del programa la importa desde aquí.

Usamos pydantic-settings: lee automáticamente el archivo .env y valida los
tipos (por ejemplo, que DEBUG sea un booleano y no el texto "true").
"""

# functools.lru_cache: "memoriza" el resultado de una función. La usamos para
# construir Settings una sola vez y reutilizar el mismo objeto en toda la app.
from functools import lru_cache

# BaseSettings: clase base de pydantic que sabe leer variables de entorno y .env.
# SettingsConfigDict: configura de dónde y cómo se leen esas variables.
from pydantic_settings import BaseSettings, SettingsConfigDict


# ──────────────────────────────────────────────────────────────────────────────
# Settings: contiene TODOS los valores de configuración de la aplicación.
# Cada atributo se llena desde la variable de entorno del mismo nombre
# (en mayúsculas), o desde el .env, o usa el valor por defecto que escribimos.
# ──────────────────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    # model_config le dice a pydantic CÓMO cargar la configuración:
    #   env_file=".env"        → lee las variables desde el archivo .env.
    #   case_sensitive=False   → DATABASE_URL y database_url son equivalentes.
    #   extra="ignore"         → si el .env trae variables que no usamos, no falla.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Aplicación ----
    app_name: str = "ClinicFlow"        # Nombre de la app (se muestra en la API).
    environment: str = "development"    # development | production.
    debug: bool = True                  # Modo depuración: logs y mensajes extra.
    seed_demo: bool = True              # Si True, puebla la BD con datos de ejemplo al arrancar.

    # ---- Base de datos ----
    # URL de conexión a PostgreSQL. Formato:
    #   postgresql+psycopg2://usuario:clave@host:puerto/nombre_bd
    # En docker-compose el host es "db"; en local suele ser "localhost".
    database_url: str = "postgresql+psycopg2://clinicflow:clinicflow@localhost:5432/clinicflow"

    # ---- Seguridad / Auth ----
    secret_key: str = "cambia-esto-por-una-clave-larga-y-aleatoria"  # Firma de tokens JWT.
    access_token_expire_minutes: int = 60  # Minutos de validez de un token de sesión.

    # ---- Telegram ----
    telegram_bot_token: str = ""  # Token del bot de Telegram (vacío hasta configurarlo).

    # ---- Modelo de lenguaje (LLM) ----
    # El asistente habla con cualquier servidor compatible con la API de OpenAI.
    # Cambiando solo estas tres variables se apunta a Groq (gratis, en la nube),
    # a un llama.cpp local, o a cualquier otro proveedor, sin tocar el código.
    #   - Groq:        https://api.groq.com/openai/v1   (modelo: llama-3.3-70b-versatile)
    #   - llama.cpp:   http://llama:8080/v1             (modelo: el que sirvas)
    llm_base_url: str = "https://api.groq.com/openai/v1"  # URL base del proveedor LLM.
    llm_api_key: str = ""                                 # Clave de API del proveedor.
    llm_model: str = "llama-3.3-70b-versatile"            # Modelo del asistente.

    @property
    def is_production(self) -> bool:
        """True si estamos en producción; útil para activar/desactivar comportamientos."""
        return self.environment.lower() == "production"


# ──────────────────────────────────────────────────────────────────────────────
# get_settings(): devuelve SIEMPRE la misma instancia de Settings.
# Gracias a @lru_cache, la configuración se lee del .env una sola vez y luego
# se reutiliza, evitando releer el archivo en cada petición.
# ──────────────────────────────────────────────────────────────────────────────

@lru_cache
def get_settings() -> Settings:
    """Crea (la primera vez) y devuelve la configuración global de la app."""
    return Settings()


# Instancia lista para importar directamente: `from ...core.config import settings`.
settings = get_settings()
