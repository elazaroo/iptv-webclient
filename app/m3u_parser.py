import re
import requests
import re
import requests
from urllib.parse import urlparse

class M3UParser:
    def __init__(self):
        self.channel_pattern = re.compile(r'#EXTINF:(.*?),(.*?)$', re.MULTILINE)
        self.attribute_pattern = re.compile(r'([a-zA-Z-]+)="([^"]*)"')
    
    def parse_m3u_content(self, content):
        """Parse M3U content and return structured data"""
        channels = []
        groups = set()
        
        lines = content.strip().split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('#EXTINF:'):
                # Obtener información del canal
                channel_info = self._parse_extinf_line(line)
                
                # Siguiente línea debería ser la URL
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and not url.startswith('#'):
                        channel_info['url'] = url
                        channels.append(channel_info)
                        
                        # Agregar grupo al set
                        if channel_info.get('group_title'):
                            groups.add(channel_info['group_title'])
                
                i += 2
            else:
                i += 1
        
        return {
            'channels': channels,
            'groups': sorted(list(groups))
        }
    
    def _parse_extinf_line(self, line):
        """Parse a single EXTINF line"""
        # Extraer duración y nombre
        match = self.channel_pattern.match(line)
        if not match:
            return {}
        
        duration_and_attrs = match.group(1)
        name = match.group(2)
        
        # Extraer atributos
        attributes = {}
        for attr_match in self.attribute_pattern.finditer(duration_and_attrs):
            key = attr_match.group(1).lower().replace('-', '_')
            value = attr_match.group(2)
            attributes[key] = value
        
        # Información del canal
        channel_info = {
            'name': name,
            'tvg_id': attributes.get('tvg_id', ''),
            'tvg_name': attributes.get('tvg_name', ''),
            'tvg_logo': attributes.get('tvg_logo', ''),
            'group_title': attributes.get('group_title', 'Sin categoría'),
            'logo': attributes.get('tvg_logo', '')
        }
        
        return channel_info
    
    def fetch_m3u_from_url(self, url):
        """Fetch M3U content from URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Detectar encoding
            encoding = response.encoding or 'utf-8'
            content = response.content.decode(encoding, errors='ignore')
            
            return content
        except Exception as e:
            raise Exception(f"Error fetching M3U from URL: {str(e)}")
    
    def validate_m3u_content(self, content):
        """Validate if content is a valid M3U file"""
        if not content:
            return False
        
        lines = content.strip().split('\n')
        
        # Debe empezar con #EXTM3U
        if not lines[0].strip().upper().startswith('#EXTM3U'):
            return False
        
        # Debe tener al menos un canal
        has_extinf = any(line.strip().startswith('#EXTINF:') for line in lines)
        
        return has_extinf
    
    def get_playlist_info(self, content):
        """Extract playlist metadata from M3U content"""
        lines = content.strip().split('\n')
        
        info = {
            'title': 'Lista IPTV',
            'description': '',
            'total_channels': 0
        }
        
        # Buscar información en las primeras líneas
        for line in lines[:10]:
            line = line.strip()
            if line.startswith('#EXTM3U'):
                # Buscar atributos en la línea EXTM3U
                attrs = {}
                for attr_match in self.attribute_pattern.finditer(line):
                    key = attr_match.group(1).lower()
                    value = attr_match.group(2)
                    attrs[key] = value
                
                if 'x-tvg-name' in attrs:
                    info['title'] = attrs['x-tvg-name']
                elif 'tvg-name' in attrs:
                    info['title'] = attrs['tvg-name']
        
        # Contar canales
        extinf_count = sum(1 for line in lines if line.strip().startswith('#EXTINF:'))
        info['total_channels'] = extinf_count
        
        return info