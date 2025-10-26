"""
Custom STAC Client supporting any STAC API endpoint
"""
from qgis.core import QgsMessageLog, Qgis
import requests
from requests.auth import HTTPBasicAuth

try:
    import pystac_client
    PYSTAC_AVAILABLE = True
except ImportError:
    PYSTAC_AVAILABLE = False


class CustomStacClient:
    """Custom STAC client for any endpoint"""
    
    def __init__(self, connection_manager):
        """Initialize with connection manager"""
        self.connection_manager = connection_manager
    
    def _get_client(self, connection):
        """Get PySTAC client for connection
        
        Args:
            connection (dict): Connection configuration
            
        Returns:
            pystac_client.Client: STAC client instance
        """
        if not PYSTAC_AVAILABLE:
            raise ImportError('pystac-client is required but not installed')
        
        url = connection['url']
        username = connection.get('username', '')
        password = connection.get('password', '')
        
        # Setup authentication if provided
        if username and password:
            session = requests.Session()
            session.auth = HTTPBasicAuth(username, password)
            return pystac_client.Client.open(url, request_session=session)
        else:
            return pystac_client.Client.open(url)
    
    def list_collections(self, connection):
        """List collections from STAC API
        
        Args:
            connection (dict): Connection configuration
            
        Returns:
            list: List of collection IDs
        """
        try:
            client = self._get_client(connection)
            collections = list(client.get_collections())
            return [col.id for col in collections]
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Failed to list collections: {str(e)}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            return []
    
    def search_items(self, connection, collections, bbox=None, 
                     datetime=None, cloud_cover=None, limit=100):
        """Search for items
        
        Args:
            connection (dict): Connection configuration
            collections (list): Collection IDs
            bbox (list): Bounding box [west, south, east, north]
            datetime (str): Date range
            cloud_cover (float): Maximum cloud cover
            limit (int): Maximum results
            
        Returns:
            list: List of STAC items
        """
        try:
            client = self._get_client(connection)
            
            # Build query
            query = {}
            if cloud_cover is not None:
                query['eo:cloud_cover'] = {'lt': cloud_cover}
            
            # Execute search
            search = client.search(
                collections=collections,
                bbox=bbox,
                datetime=datetime,
                query=query if query else None,
                limit=limit
            )
            
            items = list(search.items())
            
            QgsMessageLog.logMessage(
                f'Found {len(items)} items',
                'Open Geodata Browser',
                Qgis.Info
            )
            
            return items
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Search failed: {str(e)}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            raise
    
    def download_asset(self, asset, destination):
        """Download an asset
        
        Args:
            asset: STAC asset object
            destination (str): Download path
        """
        try:
            import urllib.request
            
            url = asset.href
            
            QgsMessageLog.logMessage(
                f'Downloading {url} to {destination}',
                'Open Geodata Browser',
                Qgis.Info
            )
            
            urllib.request.urlretrieve(url, destination)
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Download failed: {str(e)}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            raise
