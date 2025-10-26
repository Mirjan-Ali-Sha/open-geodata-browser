"""
Layer Loader for loading STAC assets as QGIS layers
"""
from qgis.core import (QgsRasterLayer, QgsProject, QgsMessageLog, 
                        Qgis, QgsRasterBandStats)


class LayerLoader:
    """Load STAC assets as QGIS layers"""
    
    def __init__(self, iface):
        """Initialize with QGIS interface
        
        Args:
            iface: QGIS interface instance
        """
        self.iface = iface

    def load_cog_layer(self, item, asset_key, layer_name=None):
        """Load Cloud-Optimized GeoTIFF as QGIS layer
        
        Args:
            item: STACItem (PySTAC Item object)
            asset_key (str): Asset identifier (e.g., 'B04', 'red')
            layer_name (str): Optional custom layer name
            
        Returns:
            QgsRasterLayer: The loaded layer
        """
        try:
            # Get asset from PySTAC item
            if not hasattr(item, 'assets') or asset_key not in item.assets:
                raise ValueError(f'Asset {asset_key} not found in item')
            
            asset = item.assets[asset_key]
            
            # Get URL from asset (PySTAC way)
            url = asset.href
            
            if layer_name is None:
                layer_name = f"{item.id}_{asset_key}"
            
            # Create QGIS raster layer with vsicurl
            vsicurl_url = f"/vsicurl/{url}"
            layer = QgsRasterLayer(vsicurl_url, layer_name, 'gdal')
            
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                
                # Apply default styling
                self.apply_default_style(layer)
                
                QgsMessageLog.logMessage(
                    f'Successfully loaded {layer_name}',
                    'Open Geodata Browser',
                    Qgis.Success
                )
                
                # Refresh canvas
                self.iface.mapCanvas().refresh()
                
                return layer
            else:
                error_msg = f'Failed to load layer from {url}'
                QgsMessageLog.logMessage(
                    error_msg,
                    'Open Geodata Browser',
                    Qgis.Critical
                )
                raise ValueError(error_msg)
                
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Error loading COG layer: {str(e)}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            raise

    def load_multiple_bands(self, item, asset_keys):
        """Load multiple bands from a single item
        
        Args:
            item: STACItem object
            asset_keys (list): List of asset keys
            
        Returns:
            list: List of loaded layers
        """
        layers = []
        for asset_key in asset_keys:
            try:
                layer = self.load_cog_layer(item, asset_key)
                layers.append(layer)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f'Failed to load {asset_key}: {str(e)}',
                    'Open Geodata Browser',
                    Qgis.Warning
                )
        return layers

    def apply_default_style(self, layer):
        """Apply default styling to raster layer
        
        Args:
            layer (QgsRasterLayer): Raster layer to style
        """
        try:
            # Get statistics
            provider = layer.dataProvider()
            stats = provider.bandStatistics(1, QgsRasterBandStats.All)
            
            # Apply basic contrast enhancement
            from qgis.core import QgsContrastEnhancement, QgsRasterMinMaxOrigin
            
            renderer = layer.renderer()
            if renderer:
                renderer.setMinMaxOrigin(QgsRasterMinMaxOrigin())
                
            layer.triggerRepaint()
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f'Could not apply default style: {str(e)}',
                'Open Geodata Browser',
                Qgis.Warning
            )
