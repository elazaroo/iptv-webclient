# IPTV WebClient

Un reproductor web moderno para listas IPTV M3U con interfaz Bootstrap y base de datos SQLite.

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

## Instalación Rápida con Docker

### Usando Docker Compose (Recomendado)

```bash
# Clonar o descargar los archivos
git clone <repository-url>
cd iptv-webclient

# Ejecutar con Docker Compose
docker-compose up -d

# Ver logs
docker-compose logs -f
```

La aplicación estará disponible en: http://localhost:3010

### Usando Docker directamente

```bash
# Construir imagen
docker build -t iptv-webclient .

# Ejecutar contenedor
docker run -d \
  --name iptv-webclient \
  -p 3010:80 \
  -v iptv_data:/app/data \
  iptv-webclient
```

## Instalación Manual

### Requisitos

- Python 3.11+
- pip

### Pasos

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
python app/main.py
```

La aplicación estará disponible en: http://localhost:3010

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
- **SQLite**: Base de datos ligera y eficiente
- **M3U Parser**: Analizador personalizado de listas M3U
- **API REST**: Endpoints para gestión de datos

### Containerización
- **Docker**: Contenedor optimizado
- **Gunicorn**: Servidor WSGI para producción
- **Multi-stage build**: Imagen optimizada
- **Volume persistence**: Datos persistentes

## API Endpoints

### Listas
- `GET /api/playlists` - Obtener todas las listas
- `POST /api/playlists` - Agregar nueva lista
- `DELETE /api/playlists/<id>` - Eliminar lista

### Canales
- `GET /api/playlists/<id>/channels` - Obtener canales de una lista
- `GET /api/playlists/<id>/groups` - Obtener grupos de una lista
- `GET /api/channels/<id>` - Obtener información de un canal

### Favoritos
- `GET /api/favorites` - Obtener favoritos
- `POST /api/favorites/<channel_id>` - Agregar a favoritos
- `DELETE /api/favorites/<channel_id>` - Quitar de favoritos

### Utilidades
- `POST /api/validate-m3u` - Validar contenido M3U

## Configuración Avanzada

### Variables de Entorno

```bash
FLASK_ENV=production          # Entorno de Flask
FLASK_APP=app/main.py        # Archivo principal
```

### Volúmenes Docker

- `/app/data` - Base de datos y archivos persistentes

### Puertos

- `3010` - Puerto web principal (externo)
- `80` - Puerto interno del contenedor

## Controles de Teclado

- **Espacio**: Reproducir/Pausar
- **F**: Pantalla completa
- **M**: Silenciar/Activar audio
- **I**: Mostrar información del canal
- **Esc**: Salir de pantalla completa

## Desarrollo

### Estructura del Proyecto

```
iptv-webclient/
├── app/
│   ├── main.py              # Aplicación principal Flask
│   ├── database.py          # Gestión de base de datos SQLite
│   ├── m3u_parser.py        # Parser de archivos M3U
│   ├── templates/           # Plantillas HTML
│   │   ├── base.html        # Plantilla base
│   │   ├── index.html       # Página principal
│   │   ├── playlist.html    # Vista de lista de canales
│   │   └── player.html      # Reproductor completo
│   └── static/              # Archivos estáticos
├── Dockerfile               # Configuración Docker
├── docker-compose.yml       # Orquestación Docker
├── requirements.txt         # Dependencias Python
└── README.md               # Este archivo
```

### Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/amazing-feature`)
3. Commit tus cambios (`git commit -m 'Add amazing feature'`)
4. Push a la rama (`git push origin feature/amazing-feature`)
5. Abre un Pull Request

## Troubleshooting

### Problemas Comunes

1. **Canal no reproduce**
   - Verifica que la URL del stream sea válida
   - Algunos streams requieren headers específicos
   - Comprueba la conectividad de red

2. **Lista M3U no se carga**
   - Verifica el formato del archivo M3U
   - Asegúrate de que la URL sea accesible
   - Revisa los logs para errores específicos

3. **Base de datos corrupta**
   - Elimina el volumen Docker: `docker volume rm iptv_data`
   - Reinicia el contenedor

### Logs

```bash
# Ver logs del contenedor
docker-compose logs -f iptv-webclient

# Ver logs en tiempo real
docker logs -f iptv-webclient
```

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## Soporte

Para soporte y preguntas:
- Crea un issue en GitHub
- Revisa la documentación existente
- Verifica los logs para errores específicos