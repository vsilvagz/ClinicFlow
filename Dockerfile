# ---- Imagen base ----
FROM python:3.11-slim

# Evita .pyc y fuerza salida sin buffer (mejores logs en contenedor).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Dependencias del sistema necesarias para psycopg2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias Python primero (mejor uso de la caché de capas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
