"""
Client Manager for Open-Geodata-API
"""
import open_geodata_api as ogapi
from qgis.core import QgsMessageLog, Qgis


class ClientManager:
    """Manages Open-Geodata-API clients"""
    
    def __init__(self):
        self.pc_client = None
        self.es_client = None
        self.clients_initialized = False

    def initialize_clients(self, pc_auto_sign=True):
        """Initialize both API clients
        
        Args:
            pc_auto_sign (bool): Automatically sign Planetary Computer URLs
            
        Returns:
            bool: True if successful
        """
        try:
            clients = ogapi.get_clients(pc_auto_sign=pc_auto_sign)
            self.pc_client = clients['planetary_computer']
            self.es_client = clients['earth_search']
            self.clients_initialized = True
            
            QgsMessageLog.logMessage(
                'Geodata API clients initialized successfully',
                'Open Geodata Browser',
                Qgis.Info
            )
            return True
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Failed to initialize clients: {str(e)}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            return False

    def get_client(self, provider='planetary_computer'):
        """Get specific client instance
        
        Args:
            provider (str): Either 'planetary_computer' or 'earth_search'
            
        Returns:
            Client instance
        """
        if not self.clients_initialized:
            raise RuntimeError('Clients not initialized. Call initialize_clients() first.')
        
        if provider == 'planetary_computer':
            return self.pc_client
        elif provider == 'earth_search':
            return self.es_client
        else:
            raise ValueError(f'Unknown provider: {provider}')

    def is_initialized(self):
        """Check if clients are initialized"""
        return self.clients_initialized
