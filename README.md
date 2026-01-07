# IPTV WebClient

Un reproductor web moderno para listas IPTV M3U con interfaz Bootstrap y base de datos SQLite.

## 🚀 Instalación Rápida

### Desde GitHub Container Registry (Recomendado)

```bash
# Método 1: Docker run directo
docker run -d \
  --name iptv-webclient \
  -p 3010:80 \
  -v iptv_data:/app/data \
  ghcr.io/elazaroo/iptv-webclient:latest

# Método 2: Con docker-compose
wget https://raw.githubusercontent.com/elazaroo/iptv-webclient/main/docker-compose.ghcr.yml
docker-compose -f docker-compose.ghcr.yml up -d
```

**Acceso:** http://localhost:3010

### Para CasaOS (Interfaz Web)

**Configuración en CasaOS:**
- **Imagen Docker:** `ghcr.io/elazaroo/iptv-webclient:latest`
- **Tag:** `latest`
- **Título:** `IPTV WebClient`
- **Icono URL:** `https://cdn-icons-png.flaticon.com/512/3039/3039011.png`
- **Web UI:** `http://<TU_IP>:3010` (ej: `http://192.168.1.10:3010`)
- **Puertos:** `3010` → `80` (TCP)
- **Volúmenes:** `/app/data` → `/DATA/AppData/iptv-webclient` (ruta absoluta)
- **Variables de entorno:**
  - `FLASK_ENV` → `production`
  - `FLASK_APP` → `app/main.py`
- **Red:** `bridge`
- **Política de reinicio:** `unless-stopped`

> ⚠️ **Importante:** CasaOS requiere rutas absolutas para los volúmenes. No uses Named Volumes como `iptv_data`, usa la ruta completa `/DATA/AppData/iptv-webclient`.

## 🛠️ Desarrollo Local

```bash
# Clonar repositorio
git clone https://github.com/elazaroo/iptv-webclient.git
cd iptv-webclient

# Ejecutar con Docker Compose
docker-compose up -d
```

## Características

- 📺 Reproductor de video moderno con Video.js
- 📱 Interfaz responsiva con Bootstrap 5
- 🗂️ Organización por categorías
- ⭐ Sistema de favoritos
- 🔍 Búsqueda de canales
- 📊 Base de datos SQLite para persistencia
- 🐳 Contenedor Docker listo para producción
- 🎮 Controles de teclado y pantalla completa
- 🔄 Actualización automática de listas desde URL

## Uso

### 1. Agregar Lista IPTV

1. Haz clic en "Agregar Lista" en la barra de navegación
2. Ingresa un nombre para tu lista
3. Proporciona la URL de tu archivo M3U o sube un archivo local
4. Haz clic en "Validar" para verificar el contenido
5. Si es válido, haz clic en "Agregar"

### 2. Navegar Canales

- Los canales se organizan automáticamente por categorías
- Usa la barra lateral para filtrar por categoría
- Utiliza el buscador para encontrar canales específicos
- Cambia entre vista de lista y grid

### 3. Reproducir Canales

- Haz clic en "Reproducir" en cualquier canal
- Usa el reproductor modal para vista rápida
- Haz clic en "Pantalla completa" para el reproductor dedicado

### 4. Favoritos

- Haz clic en el ícono de corazón para agregar/quitar favoritos
- Accede a tus favoritos desde la barra de navegación

## Formatos Soportados

- **Listas M3U/M3U8**: Formato estándar IPTV
- **Streams**: HLS (m3u8), MP4, WebM, OGG
- **Métodos de importación**: URL remota o archivo local

## Características Técnicas

### Frontend
- **Bootstrap 5**: Interfaz moderna y responsiva
- **Video.js**: Reproductor de video avanzado
- **JavaScript ES6+**: Funcionalidades dinámicas
- **Bootstrap Icons**: Iconografía moderna

### Backend
- **Flask**: Framework web Python
- **SQLite**: Base de datos embebida
- **Gunicorn**: Servidor WSGI para producción
- **Docker**: Contenedorización multiplataforma

## Actualizaciones

### Desde GitHub Container Registry
```bash
# Descargar nueva versión
docker pull ghcr.io/elazaroo/iptv-webclient:latest

# Recrear contenedor
docker-compose -f docker-compose.ghcr.yml down
docker-compose -f docker-compose.ghcr.yml up -d
```

### Desde código fuente
```bash
# Actualizar código
git pull origin main

# Reconstruir
docker-compose down
docker-compose up -d --build
```

## Solución de Problemas

### Logs del contenedor
```bash
docker logs iptv-webclient
```

### Verificar estado
```bash
docker ps | grep iptv-webclient
```

### Reiniciar aplicación
```bash
docker restart iptv-webclient
```

## Contribuir

1. Fork del proyecto
2. Crear rama para nueva característica
3. Commit de cambios
4. Push a la rama
5. Crear Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT.