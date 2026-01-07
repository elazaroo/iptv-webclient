from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_cors import CORS
from .database import Database
from .m3u_parser import M3UParser
import os
import logging
import requests

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
CORS(app)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Asegurar que el directorio de datos existe
os.makedirs('/app/data', exist_ok=True)

# Inicializar base de datos
db = Database('/app/data/iptv.db')

# Inicializar parser
parser = M3UParser()

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

# === Proxy de Streaming ===
@app.route('/api/proxy/stream/<int:channel_id>')
def proxy_stream(channel_id):
    """Proxy de streaming para evitar errores CORS"""
    try:
        channel = db.get_channel(channel_id)
        if not channel:
            return jsonify({'error': 'Canal no encontrado'}), 404
        
        stream_url = channel['url']
        return stream_proxy_response(stream_url)
    except Exception as e:
        logger.error(f"Error in proxy stream: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proxy/url')
def proxy_url():
    """Proxy de streaming por URL directa (para URLs que requieren proxy)"""
    try:
        stream_url = request.args.get('url')
        if not stream_url:
            return jsonify({'error': 'URL requerida'}), 400
        
        return stream_proxy_response(stream_url)
    except Exception as e:
        logger.error(f"Error in proxy url: {e}")
        return jsonify({'error': str(e)}), 500

def stream_proxy_response(stream_url):
    """Genera una respuesta de streaming proxy"""
    try:
        # Headers para simular un navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
            'Connection': 'keep-alive',
        }
        
        # Hacer petición al servidor remoto con streaming
        # Timeout más largo para videos grandes
        remote_response = requests.get(stream_url, headers=headers, stream=True, timeout=(10, 300))
        
        # Determinar content-type basado en extensión o header
        content_type = remote_response.headers.get('Content-Type', 'application/octet-stream')
        
        # Limpiar URL de query params para detectar extensión
        clean_url = stream_url.split('?')[0].lower()
        
        # Para archivos que no tienen content-type correcto
        if clean_url.endswith('.mkv') or 'mkv' in stream_url.lower():
            content_type = 'video/x-matroska'
        elif clean_url.endswith('.ts'):
            content_type = 'video/mp2t'
        elif clean_url.endswith('.mp4'):
            content_type = 'video/mp4'
        elif clean_url.endswith('.avi'):
            content_type = 'video/x-msvideo'
        elif clean_url.endswith('.m3u8'):
            content_type = 'application/vnd.apple.mpegurl'
        elif clean_url.endswith('.m3u'):
            content_type = 'audio/x-mpegurl'
        
        def generate():
            """Generador para streaming de chunks"""
            try:
                # Chunks más grandes para mejor rendimiento
                for chunk in remote_response.iter_content(chunk_size=65536):
                    if chunk:
                        yield chunk
            except GeneratorExit:
                remote_response.close()
            except Exception as e:
                logger.error(f"Error streaming: {e}")
                remote_response.close()
        
        # Headers de respuesta - NO incluir Content-Length para usar chunked transfer
        response_headers = {
            'Content-Type': content_type,
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Range',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Accel-Buffering': 'no',  # Deshabilitar buffering en nginx si existe
        }
        
        return Response(
            generate(),
            status=remote_response.status_code,
            headers=response_headers,
            direct_passthrough=True  # Pasar bytes directamente sin procesar
        )
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Timeout al conectar con el servidor de streaming'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in proxy: {e}")
        return jsonify({'error': f'Error de conexión: {str(e)}'}), 502

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'IPTV WebClient is running'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)