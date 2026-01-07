from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, send_from_directory
from flask_cors import CORS
from .database import Database
from .m3u_parser import M3UParser
import os
import logging
import requests
import subprocess
import threading
import time
import shutil
import hashlib
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
CORS(app)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de directorios
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
HLS_DIR = os.environ.get('HLS_DIR', '/tmp/hls')
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', '/usr/bin/ffmpeg')

# Asegurar que los directorios existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(HLS_DIR, exist_ok=True)

# Diccionario para tracking de procesos FFmpeg activos
# {stream_id: {'process': subprocess, 'last_access': timestamp, 'url': original_url}}
active_streams = {}
streams_lock = threading.Lock()

# Inicializar base de datos
db = Database(os.path.join(DATA_DIR, 'iptv.db'))

# Inicializar parser
parser = M3UParser()

def cleanup_old_streams():
    """Limpia streams que no han sido accedidos en los últimos 5 minutos"""
    while True:
        time.sleep(60)  # Verificar cada minuto
        current_time = time.time()
        streams_to_remove = []
        
        with streams_lock:
            for stream_id, stream_info in active_streams.items():
                # Si el stream no ha sido accedido en 5 minutos, terminarlo
                if current_time - stream_info['last_access'] > 300:
                    streams_to_remove.append(stream_id)
        
        for stream_id in streams_to_remove:
            stop_stream(stream_id)

def stop_stream(stream_id):
    """Detiene un stream y limpia sus archivos"""
    with streams_lock:
        if stream_id in active_streams:
            stream_info = active_streams[stream_id]
            process = stream_info.get('process')
            
            # Terminar proceso FFmpeg
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()
            
            # Eliminar directorio de HLS
            stream_dir = os.path.join(HLS_DIR, stream_id)
            if os.path.exists(stream_dir):
                try:
                    shutil.rmtree(stream_dir)
                except Exception as e:
                    logger.error(f"Error removing stream dir {stream_dir}: {e}")
            
            del active_streams[stream_id]
            logger.info(f"Stream {stream_id} stopped and cleaned up")

# Iniciar thread de limpieza
cleanup_thread = threading.Thread(target=cleanup_old_streams, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    try:
        playlists = db.get_playlists()
        return render_template('index.html', playlists=playlists)
    except Exception as e:
        logger.error(f"Error en index: {e}")
        return render_template('index.html', playlists=[])

@app.route('/api/playlists', methods=['GET'])
def get_playlists():
    try:
        playlists = db.get_playlists()
        return jsonify(playlists)
    except Exception as e:
        logger.error(f"Error getting playlists: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-m3u', methods=['POST'])
def validate_m3u():
    try:
        data = request.get_json()
        url = data.get('url')
        file_content = data.get('file_content')
        
        if not url and not file_content:
            return jsonify({'error': 'URL o contenido de archivo requerido'}), 400
        
        # Obtener contenido M3U
        if url:
            content = parser.fetch_m3u_from_url(url)
        else:
            content = file_content
        
        # Validar contenido
        if not parser.validate_m3u_content(content):
            return jsonify({'error': 'El contenido no es un archivo M3U válido'}), 400
        
        # Obtener información de la playlist
        info = parser.get_playlist_info(content)
        parsed_data = parser.parse_m3u_content(content)
        
        return jsonify({
            'valid': True,
            'info': info,
            'channels_count': len(parsed_data['channels']),
            'groups_count': len(parsed_data['groups']),
            'groups': parsed_data['groups']
        })
        
    except Exception as e:
        logger.error(f"Error validating M3U: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists', methods=['POST'])
def add_playlist():
    try:
        data = request.get_json()
        name = data.get('name')
        url = data.get('url')
        file_content = data.get('file_content')
        
        if not name:
            return jsonify({'error': 'Nombre es requerido'}), 400
        
        # Obtener contenido M3U
        if url:
            content = parser.fetch_m3u_from_url(url)
        elif file_content:
            content = file_content
        else:
            return jsonify({'error': 'URL o contenido de archivo requerido'}), 400
        
        # Validar contenido
        if not parser.validate_m3u_content(content):
            return jsonify({'error': 'El contenido no es un archivo M3U válido'}), 400
        
        # Parsear M3U
        parsed_data = parser.parse_m3u_content(content)
        
        # Crear lista en la base de datos
        playlist_id = db.add_playlist(name, url, content)
        
        # Crear grupos
        group_map = {}
        for group_name in parsed_data['groups']:
            if group_name and group_name not in group_map:
                group_id = db.add_group(playlist_id, group_name)
                group_map[group_name] = group_id
        
        # Agregar canales en batch para evitar "database is locked"
        channels_data = []
        for channel in parsed_data['channels']:
            group_id = None
            if channel.get('group_title') and channel['group_title'] in group_map:
                group_id = group_map[channel['group_title']]
            
            channels_data.append((
                playlist_id,
                group_id,
                channel['name'],
                channel['url'],
                channel.get('logo', ''),
                channel.get('tvg_id', ''),
                channel.get('tvg_name', ''),
                channel.get('group_title', '')
            ))
        
        # Insertar todos los canales en una sola transacción
        db.add_channels_batch(channels_data)
        
        return jsonify({
            'success': True,
            'message': f'Lista "{name}" agregada exitosamente',
            'playlist_id': playlist_id,
            'channels_count': len(parsed_data['channels'])
        })
        
    except Exception as e:
        logger.error(f"Error adding playlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/channels')
def get_channels(playlist_id):
    try:
        # Parámetros de paginación
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', 0, type=int)
        group_id = request.args.get('group_id', type=int)
        
        channels = db.get_channels(playlist_id, group_id=group_id, limit=limit, offset=offset)
        total = db.get_channels_count(playlist_id, group_id=group_id)
        
        return jsonify({
            'channels': channels,
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + len(channels)) < total if limit else False
        })
    except Exception as e:
        logger.error(f"Error getting channels: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/group-counts')
def get_group_counts(playlist_id):
    try:
        groups = db.get_group_counts(playlist_id)
        total_channels = db.get_channels_count(playlist_id)
        return jsonify({
            'groups': groups,
            'total_channels': total_channels
        })
    except Exception as e:
        logger.error(f"Error getting group counts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/groups')
def get_groups(playlist_id):
    try:
        groups = db.get_groups(playlist_id)
        return jsonify({'groups': groups})
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>', methods=['DELETE'])
def delete_playlist(playlist_id):
    try:
        db.delete_playlist(playlist_id)
        return jsonify({'success': True, 'message': 'Lista eliminada exitosamente'})
    except Exception as e:
        logger.error(f"Error deleting playlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites/<int:channel_id>', methods=['DELETE'])
def remove_favorite(channel_id):
    try:
        db.remove_favorite(channel_id)
        return jsonify({'success': True, 'message': 'Eliminado de favoritos'})
    except Exception as e:
        logger.error(f"Error removing favorite: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/playlist/<int:playlist_id>')
def view_playlist(playlist_id):
    try:
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            flash('Playlist no encontrada', 'error')
            return redirect(url_for('index'))
        
        # Obtener grupos con contadores (una sola query)
        groups = db.get_group_counts(playlist_id)
        total_channels = db.get_channels_count(playlist_id)
        
        # Ya NO cargamos todos los canales aquí - se cargan vía JavaScript
        return render_template('playlist.html', 
                             playlist=playlist,
                             groups=groups,
                             total_channels=total_channels,
                             channels=[])  # Lista vacía, se carga vía API
    except Exception as e:
        logger.error(f"Error viewing playlist: {e}")
        flash('Error al cargar la playlist', 'error')
        return redirect(url_for('index'))

@app.route('/player')
def player():
    try:
        channel_id = request.args.get('channel_id')
        if not channel_id:
            flash('ID de canal requerido', 'error')
            return redirect(url_for('index'))
        
        channel = db.get_channel(int(channel_id))
        if not channel:
            flash('Canal no encontrado', 'error')
            return redirect(url_for('index'))
        
        return render_template('player.html', channel=channel)
    except Exception as e:
        logger.error(f"Error loading player: {e}")
        flash('Error al cargar el reproductor', 'error')
        return redirect(url_for('index'))

@app.route('/play/<int:channel_id>')
def play_channel(channel_id):
    try:
        channel = db.get_channel(channel_id)
        if not channel:
            flash('Canal no encontrado', 'error')
            return redirect(url_for('index'))
        
        return render_template('player.html', channel=channel)
    except Exception as e:
        logger.error(f"Error playing channel: {e}")
        flash('Error al reproducir el canal', 'error')
        return redirect(url_for('index'))

@app.route('/api/favorites/<int:channel_id>', methods=['POST'])
def toggle_favorite(channel_id):
    try:
        # Aquí asumimos que toggle_favorite devuelve True si se agregó, False si se eliminó
        is_favorite = db.toggle_favorite(channel_id) if hasattr(db, 'toggle_favorite') else None
        
        if is_favorite is None:
            # Si no hay método toggle, intentamos con add/remove
            try:
                db.add_favorite(channel_id)
                message = 'Agregado a favoritos'
            except:
                try:
                    db.remove_favorite(channel_id)
                    message = 'Eliminado de favoritos'
                except:
                    message = 'Favorito actualizado'
        else:
            message = 'Agregado a favoritos' if is_favorite else 'Eliminado de favoritos'
            
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites')
def get_favorites():
    try:
        favorites = db.get_favorites()
        return jsonify({'favorites': favorites})
    except Exception as e:
        logger.error(f"Error getting favorites: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/favorites')
def favorites():
    try:
        channels = db.get_favorites()
        return render_template('favorites.html', channels=channels)
    except Exception as e:
        logger.error(f"Error getting favorites: {e}")
        return render_template('favorites.html', channels=[])

# === Sistema de Streaming HLS con FFmpeg ===

def get_stream_id(channel_id, url):
    """Genera un ID único para el stream basado en channel_id y URL"""
    hash_input = f"{channel_id}:{url}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]

def is_native_hls(url):
    """Verifica si la URL ya es un stream HLS nativo"""
    clean_url = url.split('?')[0].lower()
    return clean_url.endswith('.m3u8')

def start_ffmpeg_stream(stream_id, source_url):
    """Inicia transcoding FFmpeg para el stream"""
    stream_dir = os.path.join(HLS_DIR, stream_id)
    os.makedirs(stream_dir, exist_ok=True)
    
    playlist_path = os.path.join(stream_dir, 'playlist.m3u8')
    error_log_path = os.path.join(stream_dir, 'ffmpeg_error.log')
    
    # Comando FFmpeg optimizado - intentar copiar streams cuando sea posible
    cmd = [
        FFMPEG_PATH,
        '-y',
        '-loglevel', 'info',
        '-hide_banner',
        # Opciones de entrada con timeout
        '-timeout', '10000000',  # 10 segundos en microsegundos
        '-reconnect', '1',
        '-reconnect_streamed', '1', 
        '-reconnect_delay_max', '5',
        '-i', source_url,
        # Intentar copiar video, si falla re-codificar
        '-c:v', 'copy',
        # Audio: convertir a AAC para compatibilidad
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ac', '2',
        # Formato HLS
        '-f', 'hls',
        '-hls_time', '2',  # Segmentos más cortos para inicio más rápido
        '-hls_list_size', '10',
        '-hls_flags', 'delete_segments+append_list+omit_endlist',
        '-hls_segment_filename', os.path.join(stream_dir, 'segment_%03d.ts'),
        playlist_path
    ]
    
    logger.info(f"Starting FFmpeg for stream {stream_id}")
    logger.info(f"Source URL: {source_url}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    # Abrir archivo de log para errores
    error_log = open(error_log_path, 'w')
    
    # Iniciar FFmpeg en background
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=error_log,
        stdin=subprocess.DEVNULL
    )
    
    # Registrar en active_streams
    with streams_lock:
        active_streams[stream_id] = {
            'process': process,
            'last_access': time.time(),
            'url': source_url,
            'dir': stream_dir,
            'error_log': error_log_path
        }
    
    return playlist_path

def get_ffmpeg_error(stream_id):
    """Obtiene el error de FFmpeg si existe"""
    with streams_lock:
        if stream_id in active_streams:
            error_log_path = active_streams[stream_id].get('error_log')
            if error_log_path and os.path.exists(error_log_path):
                try:
                    with open(error_log_path, 'r') as f:
                        return f.read()[-2000:]  # Últimos 2000 caracteres
                except:
                    pass
    return None

def check_ffmpeg_status(stream_id):
    """Verifica el estado de FFmpeg y retorna información de diagnóstico"""
    with streams_lock:
        if stream_id not in active_streams:
            return {'status': 'not_found', 'error': 'Stream no encontrado'}
        
        stream_info = active_streams[stream_id]
        process = stream_info.get('process')
        
        if process is None:
            return {'status': 'no_process', 'error': 'No hay proceso FFmpeg'}
        
        poll_result = process.poll()
        
        if poll_result is None:
            # Proceso aún corriendo
            return {'status': 'running', 'pid': process.pid}
        else:
            # Proceso terminó
            error = get_ffmpeg_error(stream_id)
            return {
                'status': 'exited',
                'exit_code': poll_result,
                'error': error
            }

def wait_for_playlist(playlist_path, timeout=30):
    """Espera hasta que el playlist HLS esté disponible"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(playlist_path):
            # Verificar que tiene al menos un segmento
            try:
                with open(playlist_path, 'r') as f:
                    content = f.read()
                    if '.ts' in content:
                        return True
            except:
                pass
        time.sleep(0.5)
    return False

@app.route('/api/stream/<int:channel_id>/playlist.m3u8')
def hls_playlist(channel_id):
    """Sirve el playlist HLS para un canal"""
    try:
        channel = db.get_channel(channel_id)
        if not channel:
            return jsonify({'error': 'Canal no encontrado'}), 404
        
        source_url = channel['url']
        
        # Si ya es HLS nativo, redirigir con proxy
        if is_native_hls(source_url):
            return proxy_m3u8(source_url)
        
        # Generar stream_id único
        stream_id = get_stream_id(channel_id, source_url)
        stream_dir = os.path.join(HLS_DIR, stream_id)
        playlist_path = os.path.join(stream_dir, 'playlist.m3u8')
        
        # Verificar si el stream ya está activo
        with streams_lock:
            if stream_id in active_streams:
                # Actualizar timestamp de acceso
                active_streams[stream_id]['last_access'] = time.time()
                
                # Si el proceso murió, reiniciarlo
                process = active_streams[stream_id].get('process')
                if process and process.poll() is not None:
                    logger.warning(f"Stream {stream_id} died, restarting...")
                    del active_streams[stream_id]
                    start_ffmpeg_stream(stream_id, source_url)
            else:
                # Iniciar nuevo stream
                start_ffmpeg_stream(stream_id, source_url)
        
        # Esperar a que el playlist esté disponible
        if not wait_for_playlist(playlist_path, timeout=20):
            # Verificar qué pasó con FFmpeg
            ffmpeg_status = check_ffmpeg_status(stream_id)
            error_msg = f"Timeout esperando transcoding. FFmpeg status: {ffmpeg_status.get('status')}"
            if ffmpeg_status.get('error'):
                error_msg += f"\nFFmpeg error: {ffmpeg_status.get('error')[:500]}"
            logger.error(error_msg)
            return jsonify({
                'error': 'Timeout esperando inicio de transcoding',
                'ffmpeg_status': ffmpeg_status
            }), 504
        
        # Leer y modificar el playlist para usar rutas relativas correctas
        try:
            with open(playlist_path, 'r') as f:
                content = f.read()
            
            # Reemplazar rutas de segmentos para que usen nuestra API
            content = content.replace(
                stream_dir + '/',
                f'/api/stream/{channel_id}/segments/'
            )
            content = content.replace(
                'segment_',
                f'/api/stream/{channel_id}/segments/segment_'
            )
            
            response = Response(content, mimetype='application/vnd.apple.mpegurl')
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache'
            return response
            
        except Exception as e:
            logger.error(f"Error reading playlist: {e}")
            return jsonify({'error': 'Error leyendo playlist'}), 500
            
    except Exception as e:
        logger.error(f"Error in hls_playlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream/<int:channel_id>/segments/<segment>')
def hls_segment(channel_id, segment):
    """Sirve un segmento HLS"""
    try:
        channel = db.get_channel(channel_id)
        if not channel:
            return jsonify({'error': 'Canal no encontrado'}), 404
        
        source_url = channel['url']
        stream_id = get_stream_id(channel_id, source_url)
        stream_dir = os.path.join(HLS_DIR, stream_id)
        
        # Actualizar timestamp de acceso
        with streams_lock:
            if stream_id in active_streams:
                active_streams[stream_id]['last_access'] = time.time()
        
        # Servir el segmento
        if os.path.exists(os.path.join(stream_dir, segment)):
            response = send_from_directory(stream_dir, segment)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache'
            return response
        else:
            return jsonify({'error': 'Segmento no encontrado'}), 404
            
    except Exception as e:
        logger.error(f"Error serving segment: {e}")
        return jsonify({'error': str(e)}), 500

def proxy_m3u8(url):
    """Proxy para playlists M3U8 nativos"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        # Modificar URLs relativas en el playlist
        content = response.text
        base_url = url.rsplit('/', 1)[0] + '/'
        
        # Convertir rutas relativas a absolutas
        lines = content.split('\n')
        modified_lines = []
        for line in lines:
            if line.strip() and not line.startswith('#'):
                if not line.startswith('http'):
                    # Es una ruta relativa, convertir a absoluta
                    line = base_url + line
                # Usar nuestro proxy para cada URL
                line = f'/api/proxy/url?url={line}'
            modified_lines.append(line)
        
        modified_content = '\n'.join(modified_lines)
        
        resp = Response(modified_content, mimetype='application/vnd.apple.mpegurl')
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
        
    except Exception as e:
        logger.error(f"Error proxying m3u8: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proxy/url')
def proxy_url():
    """Proxy simple para URLs (usado para segmentos de HLS nativo)"""
    try:
        stream_url = request.args.get('url')
        if not stream_url:
            return jsonify({'error': 'URL requerida'}), 400
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        remote_response = requests.get(stream_url, headers=headers, stream=True, timeout=(10, 60))
        
        def generate():
            for chunk in remote_response.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        
        response_headers = {
            'Content-Type': remote_response.headers.get('Content-Type', 'video/mp2t'),
            'Access-Control-Allow-Origin': '*',
        }
        
        return Response(generate(), headers=response_headers)
        
    except Exception as e:
        logger.error(f"Error in proxy url: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream/<int:channel_id>/stop')
def stop_channel_stream(channel_id):
    """Detiene manualmente un stream"""
    try:
        channel = db.get_channel(channel_id)
        if not channel:
            return jsonify({'error': 'Canal no encontrado'}), 404
        
        stream_id = get_stream_id(channel_id, channel['url'])
        stop_stream(stream_id)
        
        return jsonify({'success': True, 'message': 'Stream detenido'})
    except Exception as e:
        logger.error(f"Error stopping stream: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream/<int:channel_id>/debug')
def debug_stream(channel_id):
    """Endpoint de diagnóstico para un stream específico"""
    try:
        channel = db.get_channel(channel_id)
        if not channel:
            return jsonify({'error': 'Canal no encontrado'}), 404
        
        stream_id = get_stream_id(channel_id, channel['url'])
        stream_dir = os.path.join(HLS_DIR, stream_id)
        
        # Información de diagnóstico
        debug_info = {
            'channel_id': channel_id,
            'channel_url': channel['url'],
            'stream_id': stream_id,
            'stream_dir': stream_dir,
            'ffmpeg_path': FFMPEG_PATH,
            'ffmpeg_exists': os.path.exists(FFMPEG_PATH),
            'hls_dir_exists': os.path.exists(HLS_DIR),
            'stream_dir_exists': os.path.exists(stream_dir),
        }
        
        # Archivos en el directorio del stream
        if os.path.exists(stream_dir):
            debug_info['files'] = os.listdir(stream_dir)
        
        # Estado de FFmpeg
        debug_info['ffmpeg_status'] = check_ffmpeg_status(stream_id)
        
        # Streams activos
        with streams_lock:
            debug_info['active_streams'] = list(active_streams.keys())
        
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error in debug: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'IPTV WebClient is running'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)