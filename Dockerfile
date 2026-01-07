FROM python:3.11-slim

# Instalar dependencias del sistema incluyendo FFmpeg
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de aplicación
COPY app/ ./app/
COPY . .

# Crear directorios para datos y streams HLS
RUN mkdir -p /app/data /tmp/hls

# Exponer puerto
EXPOSE 80

# Variables de entorno para FFmpeg
ENV FFMPEG_PATH=/usr/bin/ffmpeg
ENV HLS_DIR=/tmp/hls

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Comando de inicio con más workers para manejar streams
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "4", "--threads", "4", "--timeout", "300", "--pythonpath", "/app", "app.main:app"]