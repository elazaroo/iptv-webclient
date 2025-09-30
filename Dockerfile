FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY app/ ./app/

# Crear directorio para la base de datos
RUN mkdir -p /app/data

# Exponer puerto 80
EXPOSE 80

# Configurar variables de entorno
ENV FLASK_APP=app/main.py
ENV FLASK_ENV=production

# Comando para ejecutar la aplicación
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "4", "app.main:app"]