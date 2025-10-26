"""
Connection Manager for STAC API endpoints
"""
import json
from qgis.PyQt.QtCore import QSettings
from qgis.core import QgsMessageLog, Qgis, QgsAuthMethodConfig
from qgis.core import QgsApplication


class ConnectionManager:
    """Manage STAC API connections with credentials"""
    
    SETTINGS_KEY = 'OpenGeodataBrowser/connections'
    
    # Default connections
    DEFAULT_CONNECTIONS = {
        'Planetary Computer': {
            'url': 'https://planetarycomputer.microsoft.com/api/stac/v1',
            'username': '',
            'password': '',
            'auto_sign': True
        },
        'AWS EarthSearch': {
            'url': 'https://earth-search.aws.element84.com/v1',
            'username': '',
            'password': '',
            'auto_sign': False
        }
    }
    
    def __init__(self):
        """Initialize connection manager"""
        self.settings = QSettings()
        self._ensure_defaults()
    
    def _ensure_defaults(self):
        """Ensure default connections exist"""
        existing = self.get_all_connections()
        if not existing:
            for name, config in self.DEFAULT_CONNECTIONS.items():
                self.save_connection(name, config)
    
    def get_all_connections(self):
        """Get all saved connections
        
        Returns:
            dict: Dictionary of connection name -> connection config
        """
        connections_json = self.settings.value(self.SETTINGS_KEY, '{}')
        try:
            if isinstance(connections_json, str):
                return json.loads(connections_json) if connections_json else {}
            return connections_json
        except json.JSONDecodeError:
            QgsMessageLog.logMessage(
                'Failed to parse connections settings',
                'Open Geodata Browser',
                Qgis.Warning
            )
            return {}
    
    def get_connection(self, name):
        """Get a specific connection by name
        
        Args:
            name (str): Connection name
            
        Returns:
            dict: Connection configuration or None
        """
        connections = self.get_all_connections()
        return connections.get(name)
    
    def save_connection(self, name, config):
        """Save a connection
        
        Args:
            name (str): Connection name
            config (dict): Connection configuration with keys:
                - url (str): API endpoint URL
                - username (str): Username (optional)
                - password (str): Password (optional)
                - auto_sign (bool): Auto-sign URLs (optional)
        """
        connections = self.get_all_connections()
        connections[name] = {
            'url': config.get('url', ''),
            'username': config.get('username', ''),
            'password': config.get('password', ''),
            'auto_sign': config.get('auto_sign', False)
        }
        
        self.settings.setValue(self.SETTINGS_KEY, json.dumps(connections))
        
        QgsMessageLog.logMessage(
            f'Connection "{name}" saved',
            'Open Geodata Browser',
            Qgis.Info
        )
    
    def delete_connection(self, name):
        """Delete a connection
        
        Args:
            name (str): Connection name
        """
        connections = self.get_all_connections()
        if name in connections:
            del connections[name]
            self.settings.setValue(self.SETTINGS_KEY, json.dumps(connections))
            
            QgsMessageLog.logMessage(
                f'Connection "{name}" deleted',
                'Open Geodata Browser',
                Qgis.Info
            )
    
    def get_connection_names(self):
        """Get list of all connection names
        
        Returns:
            list: List of connection names
        """
        return list(self.get_all_connections().keys())
    
    def test_connection(self, config):
        """Test a connection
        
        Args:
            config (dict): Connection configuration
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            import pystac_client
            from requests.auth import HTTPBasicAuth
            
            url = config.get('url', '')
            username = config.get('username', '')
            password = config.get('password', '')
            
            # Prepare authentication if provided
            auth = None
            if username and password:
                auth = HTTPBasicAuth(username, password)
            
            # Try to open the catalog
            if auth:
                import requests
                session = requests.Session()
                session.auth = auth
                catalog = pystac_client.Client.open(url, request_session=session)
            else:
                catalog = pystac_client.Client.open(url)
            
            # Try to get collections as a basic test
            collections = list(catalog.get_collections())
            
            return (True, f'Connection successful! Found {len(collections)} collections.')
            
        except Exception as e:
            return (False, f'Connection failed: {str(e)}')
