import sqlite3
import os
from datetime import datetime

class Database:
    def __init__(self, db_path='data/iptv.db'):
        self.db_path = db_path
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()
    
    def get_connection(self):
        # Timeout de 30 segundos para evitar "database is locked"
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Habilitar WAL mode para mejor concurrencia
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def init_db(self):
        """Inicializar la base de datos con las tablas necesarias"""
        conn = self.get_connection()
        try:
            # Tabla para las listas M3U
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT,
                    file_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla para los grupos/categorías
            conn.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla para los canales
            conn.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    group_id INTEGER,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    logo TEXT,
                    tvg_id TEXT,
                    tvg_name TEXT,
                    group_title TEXT,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla para favoritos
            conn.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
        finally:
            conn.close()
    
    def add_playlist(self, name, url=None, file_content=None):
        """Agregar una nueva lista de reproducción"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                'INSERT INTO playlists (name, url, file_content) VALUES (?, ?, ?)',
                (name, url, file_content)
            )
            playlist_id = cursor.lastrowid
            conn.commit()
            return playlist_id
        finally:
            conn.close()
    
    def get_playlists(self):
        """Obtener todas las listas de reproducción"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT * FROM playlists ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_playlist(self, playlist_id):
        """Obtener una lista específica"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT * FROM playlists WHERE id = ?', (playlist_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def add_group(self, playlist_id, name):
        """Agregar un grupo/categoría"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                'INSERT INTO groups (playlist_id, name) VALUES (?, ?)',
                (playlist_id, name)
            )
            group_id = cursor.lastrowid
            conn.commit()
            return group_id
        finally:
            conn.close()
    
    def get_groups(self, playlist_id):
        """Obtener grupos de una lista"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                'SELECT * FROM groups WHERE playlist_id = ? ORDER BY name',
                (playlist_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def add_channel(self, playlist_id, name, url, group_id=None, logo=None, tvg_id=None, tvg_name=None, group_title=None):
        """Agregar un canal"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                '''INSERT INTO channels 
                   (playlist_id, group_id, name, url, logo, tvg_id, tvg_name, group_title) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (playlist_id, group_id, name, url, logo, tvg_id, tvg_name, group_title)
            )
            channel_id = cursor.lastrowid
            conn.commit()
            return channel_id
        finally:
            conn.close()
    
    def add_channels_batch(self, channels_data):
        """Agregar múltiples canales en una sola transacción"""
        conn = self.get_connection()
        try:
            conn.executemany(
                '''INSERT INTO channels 
                   (playlist_id, group_id, name, url, logo, tvg_id, tvg_name, group_title) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                channels_data
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_channels(self, playlist_id, group_id=None):
        """Obtener canales de una lista o grupo"""
        conn = self.get_connection()
        try:
            if group_id:
                cursor = conn.execute(
                    'SELECT * FROM channels WHERE playlist_id = ? AND group_id = ? ORDER BY name',
                    (playlist_id, group_id)
                )
            else:
                cursor = conn.execute(
                    'SELECT * FROM channels WHERE playlist_id = ? ORDER BY name',
                    (playlist_id,)
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_channel(self, channel_id):
        """Obtener un canal específico"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT * FROM channels WHERE id = ?', (channel_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def delete_playlist(self, playlist_id):
        """Eliminar una lista de reproducción"""
        conn = self.get_connection()
        try:
            conn.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
            conn.commit()
        finally:
            conn.close()
    
    def add_favorite(self, channel_id):
        """Agregar canal a favoritos"""
        conn = self.get_connection()
        try:
            conn.execute('INSERT INTO favorites (channel_id) VALUES (?)', (channel_id,))
            conn.commit()
        finally:
            conn.close()
    
    def remove_favorite(self, channel_id):
        """Quitar canal de favoritos"""
        conn = self.get_connection()
        try:
            conn.execute('DELETE FROM favorites WHERE channel_id = ?', (channel_id,))
            conn.commit()
        finally:
            conn.close()
    
    def get_favorites(self):
        """Obtener canales favoritos"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                '''SELECT c.*, f.created_at as favorited_at 
                   FROM channels c 
                   JOIN favorites f ON c.id = f.channel_id 
                   ORDER BY f.created_at DESC'''
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def toggle_favorite(self, channel_id):
        """Toggle favorito de un canal. Retorna True si se agregó, False si se eliminó"""
        conn = self.get_connection()
        try:
            # Verificar si ya está en favoritos
            cursor = conn.execute('SELECT id FROM favorites WHERE channel_id = ?', (channel_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Eliminar de favoritos
                conn.execute('DELETE FROM favorites WHERE channel_id = ?', (channel_id,))
                conn.commit()
                return False
            else:
                # Agregar a favoritos
                conn.execute('INSERT INTO favorites (channel_id) VALUES (?)', (channel_id,))
                conn.commit()
                return True
        finally:
            conn.close()
    
    def is_favorite(self, channel_id):
        """Verificar si un canal está en favoritos"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT id FROM favorites WHERE channel_id = ?', (channel_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()