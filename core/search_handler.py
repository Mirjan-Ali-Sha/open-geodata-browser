"""
Search Handler for STAC API searches
"""
from qgis.core import QgsMessageLog, Qgis, QgsRectangle


class SearchHandler:
    """Handles search operations using Open-Geodata-API"""
    
    def __init__(self, client_manager):
        """Initialize with client manager
        
        Args:
            client_manager (ClientManager): Client manager instance
        """
        self.client_manager = client_manager

    def search_items(self, provider, collections, bbox=None, 
                     datetime=None, cloud_cover=None, limit=100):
        """Perform search using Open-Geodata-API
        
        Args:
            provider (str): 'planetary_computer' or 'earth_search'
            collections (list): List of collection IDs
            bbox (list): Bounding box [west, south, east, north]
            datetime (str): Date range string
            cloud_cover (float): Maximum cloud cover percentage
            limit (int): Maximum results
            
        Returns:
            list: List of STACItem objects
        """
        try:
            client = self.client_manager.get_client(provider)
            
            # Build query
            query = {}
            if cloud_cover is not None:
                query['eo:cloud_cover'] = {'lt': cloud_cover}
            
            # Execute search
            QgsMessageLog.logMessage(
                f'Searching {provider} - Collections: {collections}',
                'Open Geodata Browser',
                Qgis.Info
            )
            
            results = client.search(
                collections=collections,
                bbox=bbox,
                datetime=datetime,
                query=query if query else None,
                limit=limit
            )
            
            # Get items
            items = results.get_all_items()
            
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

    def get_collections(self, provider):
        """Get available collections for provider
        
        Args:
            provider (str): Provider name
            
        Returns:
            list: List of collection IDs
        """
        try:
            client = self.client_manager.get_client(provider)
            return client.list_collections()
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Failed to get collections: {str(e)}',
                'Open Geodata Browser',
                Qgis.Warning
            )
            return []
