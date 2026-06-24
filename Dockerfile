# ---- Imagen base ----
FROM python:3.11-slim

# Evita .pyc y fuerza salida sin buffer (mejores logs en contenedor).
# TZ deja al contenedor en hora de Chile, para que datetime.now() sea coherente
# con las fechas locales que maneja la app (slots, citas, chequeo de pasado).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Santiago

WORKDIR /code

# Dependencias del sistema necesarias para psycopg2 y la zona horaria (tzdata).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev tzdata \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias Python primero (mejor uso de la caché de capas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación.
COPY . .

EXPOSE 8000

# Formato shell (no exec) para que ${PORT} se expanda: plataformas como Railway o
# Render inyectan el puerto por la variable PORT. En local/compose, sin PORT, usa 8000.
CMD uvicorn app.backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
