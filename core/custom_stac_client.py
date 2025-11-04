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
    
    def get_collection_info(self, connection, collection_id):
        """Get detailed information about a collection using open-geodata-api
        
        Args:
            connection: Connection dictionary with 'url', 'username', 'password'
            collection_id: Collection identifier
            
        Returns:
            dict: Collection information
        """
        try:
            import open_geodata_api as ogapi
            
            # Determine which client to use based on URL
            url = connection['url'].lower()
            
            if 'planetarycomputer' in url:
                # Use Planetary Computer client with auto-signing
                client = ogapi.planetary_computer(auto_sign=True)
            elif 'earth-search' in url or 'element84' in url:
                # Use Earth Search client
                client = ogapi.earth_search()
            else:
                # Use generic STAC client for custom endpoints
                client = ogapi.stac(
                    stac_endpoint=connection['url'],
                    username=connection.get('username'),
                    password=connection.get('password')
                )
            
            # Get collection info
            collection_info = client.get_collection_info(collection_id)
            
            return collection_info
            
        except Exception as e:
            raise Exception(f'Failed to get collection info: {str(e)}')


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
    
    def search_items(self, connection, collections, bbox, start_date, end_date, cloud_cover=100, limit=50):
        """Search for STAC items using open-geodata-api
        
        Args:
            connection: Connection dictionary
            collections: List of collection IDs
            bbox: Bounding box [west, south, east, north]
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            cloud_cover: Maximum cloud cover percentage (default: 100)
            limit: Maximum number of results (default: 50)
            
        Returns:
            list: List of STAC items
        """
        try:
            import open_geodata_api as ogapi
            
            # Determine which client to use
            url = connection['url'].lower()
            
            if 'planetarycomputer' in url:
                client = ogapi.planetary_computer(auto_sign=True)
            elif 'earth-search' in url or 'element84' in url:
                client = ogapi.earth_search()
            else:
                client = ogapi.stac(
                    stac_endpoint=connection['url'],
                    username=connection.get('username'),
                    password=connection.get('password')
                )
            
            # Format datetime range
            datetime_range = f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"
            
            # Build query for cloud cover filter
            query = {
                "eo:cloud_cover": {
                    "lt": cloud_cover
                }
            }
            
            # Search for items - returns STACSearch object
            search_results = client.search(
                collections=collections,
                bbox=bbox,
                datetime=datetime_range,
                query=query,
                limit=limit
            )
            
            # Get all items from the search results
            items = search_results.get_all_items()
            
            return items
            
        except Exception as e:
            raise Exception(f'Search failed: {str(e)}')

    
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
