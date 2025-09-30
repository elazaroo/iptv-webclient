from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
import os
from database import Database
from m3u_parser import M3UParser

app = Flask(__name__)
app.secret_key = 'iptv-webclient-secret-key-2023'
CORS(app)

# Inicializar base de datos y parser
db = Database()
parser = M3UParser()

@app.route('/')
def index():
    """Página principal"""
    playlists = db.get_playlists()
    return render_template('index.html', playlists=playlists)

@app.route('/player')
def player():
    """Página del reproductor"""
    channel_id = request.args.get('channel_id')
    if not channel_id:
        flash('Canal no especificado', 'error')
        return redirect(url_for('index'))
    
    channel = db.get_channel(channel_id)
    if not channel:
        flash('Canal no encontrado', 'error')
        return redirect(url_for('index'))
    
    return render_template('player.html', channel=channel)

@app.route('/playlist/<int:playlist_id>')
def view_playlist(playlist_id):
    """Ver canales de una lista específica"""
    playlist = db.get_playlist(playlist_id)
    if not playlist:
        flash('Lista no encontrada', 'error')
        return redirect(url_for('index'))
    
    groups = db.get_groups(playlist_id)
    selected_group = request.args.get('group_id')
    
    if selected_group:
        channels = db.get_channels(playlist_id, selected_group)
    else:
        channels = db.get_channels(playlist_id)
    
    return render_template('playlist.html', 
                         playlist=playlist, 
                         groups=groups, 
                         channels=channels,
                         selected_group=selected_group)

# API Routes
@app.route('/api/playlists', methods=['GET'])
def api_get_playlists():
    """API: Obtener todas las listas"""
    playlists = db.get_playlists()
    return jsonify(playlists)

@app.route('/api/playlists', methods=['POST'])
def api_add_playlist():
    """API: Agregar nueva lista M3U"""
    try:
        data = request.get_json()
        name = data.get('name')
        url = data.get('url')
        file_content = data.get('file_content')
        
        if not name:
            return jsonify({'error': 'Nombre requerido'}), 400
        
        # Obtener contenido M3U
        m3u_content = None
        if url:
            try:
                m3u_content = parser.fetch_m3u_from_url(url)
            except Exception as e:
                return jsonify({'error': f'Error al obtener M3U desde URL: {str(e)}'}), 400
        elif file_content:
            m3u_content = file_content
        else:
            return jsonify({'error': 'URL o contenido del archivo requerido'}), 400
        
        # Validar contenido M3U
        if not parser.validate_m3u_content(m3u_content):
            return jsonify({'error': 'Contenido M3U inválido'}), 400
        
        # Parsear M3U
        parsed_data = parser.parse_m3u_content(m3u_content)
        
        # Crear lista en la base de datos
        playlist_id = db.add_playlist(name, url, m3u_content)
        
        # Crear grupos
        group_map = {}
        for group_name in parsed_data['groups']:
            group_id = db.add_group(playlist_id, group_name)
            group_map[group_name] = group_id
        
        # Crear canales
        for channel_data in parsed_data['channels']:
            group_id = group_map.get(channel_data['group_title'])
            db.add_channel(
                playlist_id=playlist_id,
                name=channel_data['name'],
                url=channel_data['url'],
                group_id=group_id,
                logo=channel_data.get('logo'),
                tvg_id=channel_data.get('tvg_id'),
                tvg_name=channel_data.get('tvg_name'),
                group_title=channel_data.get('group_title')
            )
        
        return jsonify({
            'success': True,
            'playlist_id': playlist_id,
            'channels_count': len(parsed_data['channels']),
            'groups_count': len(parsed_data['groups'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>', methods=['DELETE'])
def api_delete_playlist(playlist_id):
    """API: Eliminar lista"""
    try:
        db.delete_playlist(playlist_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/groups', methods=['GET'])
def api_get_groups(playlist_id):
    """API: Obtener grupos de una lista"""
    groups = db.get_groups(playlist_id)
    return jsonify(groups)

@app.route('/api/playlists/<int:playlist_id>/channels', methods=['GET'])
def api_get_channels(playlist_id):
    """API: Obtener canales de una lista o grupo"""
    group_id = request.args.get('group_id')
    channels = db.get_channels(playlist_id, group_id)
    return jsonify(channels)

@app.route('/api/channels/<int:channel_id>', methods=['GET'])
def api_get_channel(channel_id):
    """API: Obtener información de un canal"""
    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({'error': 'Canal no encontrado'}), 404
    return jsonify(channel)

@app.route('/api/favorites', methods=['GET'])
def api_get_favorites():
    """API: Obtener canales favoritos"""
    favorites = db.get_favorites()
    return jsonify(favorites)

@app.route('/api/favorites/<int:channel_id>', methods=['POST'])
def api_add_favorite(channel_id):
    """API: Agregar canal a favoritos"""
    try:
        db.add_favorite(channel_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites/<int:channel_id>', methods=['DELETE'])
def api_remove_favorite(channel_id):
    """API: Quitar canal de favoritos"""
    try:
        db.remove_favorite(channel_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-m3u', methods=['POST'])
def api_validate_m3u():
    """API: Validar contenido M3U"""
    try:
        data = request.get_json()
        url = data.get('url')
        content = data.get('content')
        
        if url:
            try:
                content = parser.fetch_m3u_from_url(url)
            except Exception as e:
                return jsonify({'valid': False, 'error': str(e)})
        
        if not content:
            return jsonify({'valid': False, 'error': 'Contenido vacío'})
        
        is_valid = parser.validate_m3u_content(content)
        
        if is_valid:
            info = parser.get_playlist_info(content)
            parsed_data = parser.parse_m3u_content(content)
            return jsonify({
                'valid': True,
                'info': info,
                'channels_count': len(parsed_data['channels']),
                'groups_count': len(parsed_data['groups'])
            })
        else:
            return jsonify({'valid': False, 'error': 'Formato M3U inválido'})
            
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)