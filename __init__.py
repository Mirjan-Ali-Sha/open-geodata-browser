"""
Open Geodata Browser - QGIS Plugin
Provides access to satellite imagery from multiple STAC providers
"""

def classFactory(iface):
    """Load GeodataBrowser class from file geodata_browser.
    
    Args:
        iface (QgsInterface): A QGIS interface instance.
    """
    from .geodata_browser import GeodataBrowser
    return GeodataBrowser(iface)
