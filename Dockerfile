# ---------------------------------------------------------------------------
# CampusRadar — imagen de producción.
# Imagen ligera basada en Python 3.12; sin pasos de build manuales.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Buenas prácticas: sin .pyc, salida sin buffer (logs en vivo).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias primero para aprovechar la caché de capas de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación.
COPY app/ ./app/
COPY static/ ./static/

# Por defecto se cargan datos demo; se puede desactivar con SEED_ON_STARTUP=false.
ENV SEED_ON_STARTUP=true

EXPOSE 8000

# Arranque del servidor ASGI.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
