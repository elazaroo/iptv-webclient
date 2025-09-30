from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
from .database import Database
from .m3u_parser import M3UParser
import os
import logging

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
db.init_db()

# Inicializar parser
parser = M3UParser()

@app.route('/')
def index():
    try:
        playlists = db.get_all_playlists()
        return render_template('index.html', playlists=playlists)
    except Exception as e:
        logger.error(f"Error en index: {e}")
        return render_template('index.html', playlists=[])

@app.route('/api/playlists', methods=['GET'])
def get_playlists():
    try:
        playlists = db.get_all_playlists()
        return jsonify({'playlists': playlists})
    except Exception as e:
        logger.error(f"Error getting playlists: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists', methods=['POST'])
def add_playlist():
    try:
        data = request.get_json()
        name = data.get('name')
        url = data.get('url')
        
        if not name or not url:
            return jsonify({'error': 'Nombre y URL son requeridos'}), 400
        
        # Validar y parsear M3U
        try:
            content = parser.fetch_m3u(url)
            channels = parser.parse_m3u_content(content)
            
            if not channels:
                return jsonify({'error': 'No se encontraron canales válidos en la URL'}), 400
                
        except Exception as e:
            return jsonify({'error': f'Error al procesar M3U: {str(e)}'}), 400
        
        # Agregar playlist a la base de datos
        playlist_id = db.add_playlist(name, url)
        
        # Agregar canales
        for channel in channels:
            db.add_channel(
                playlist_id=playlist_id,
                name=channel['name'],
                url=channel['url'],
                logo=channel.get('logo', ''),
                group=channel.get('group', 'Sin categoría')
            )
        
        return jsonify({'message': f'Playlist "{name}" agregada exitosamente', 'playlist_id': playlist_id})
        
    except Exception as e:
        logger.error(f"Error adding playlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/channels')
def get_channels(playlist_id):
    try:
        channels = db.get_channels_by_playlist(playlist_id)
        return jsonify({'channels': channels})
    except Exception as e:
        logger.error(f"Error getting channels: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/playlist/<int:playlist_id>')
def view_playlist(playlist_id):
    try:
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            flash('Playlist no encontrada', 'error')
            return redirect(url_for('index'))
        
        channels = db.get_channels_by_playlist(playlist_id)
        groups = db.get_groups_by_playlist(playlist_id)
        
        return render_template('playlist.html', 
                             playlist=playlist, 
                             channels=channels, 
                             groups=groups)
    except Exception as e:
        logger.error(f"Error viewing playlist: {e}")
        flash('Error al cargar la playlist', 'error')
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
        db.toggle_favorite(channel_id)
        return jsonify({'message': 'Favorito actualizado'})
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/favorites')
def favorites():
    try:
        channels = db.get_favorite_channels()
        return render_template('favorites.html', channels=channels)
    except Exception as e:
        logger.error(f"Error getting favorites: {e}")
        return render_template('favorites.html', channels=[])

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'IPTV WebClient is running'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)