"""
Asset Manager for downloading and managing STAC assets
"""
import os
from open_geodata_api.utils import download_single_file
from qgis.core import QgsMessageLog, Qgis


class AssetManager:
    """Manages STAC asset operations"""
    
    def download_assets(self, item, asset_keys, destination_dir):
        """Download assets from STAC item
        
        Args:
            item: STACItem object
            asset_keys (list): List of asset keys to download
            destination_dir (str): Destination directory
        """
        downloaded = []
        failed = []
        
        for asset_key in asset_keys:
            try:
                # Get asset URL
                url = item.get_asset_url(asset_key)
                
                # Create filename
                filename = f"{item.id}_{asset_key}.tif"
                filepath = os.path.join(destination_dir, filename)
                
                # Download
                QgsMessageLog.logMessage(
                    f'Downloading {asset_key} to {filepath}',
                    'Open Geodata Browser',
                    Qgis.Info
                )
                
                download_single_file(
                    url,
                    destination=filepath,
                    provider=getattr(item, 'provider', 'planetary_computer')
                )
                
                downloaded.append(asset_key)
                
            except Exception as e:
                QgsMessageLog.logMessage(
                    f'Failed to download {asset_key}: {str(e)}',
                    'Open Geodata Browser',
                    Qgis.Warning
                )
                failed.append(asset_key)
        
        return downloaded, failed
