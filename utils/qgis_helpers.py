"""
Helper utilities for QGIS operations
"""
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                        QgsRectangle, QgsProject)


def transform_bbox_to_wgs84(bbox, source_crs):
    """Transform bounding box to WGS84
    
    Args:
        bbox (QgsRectangle): Bounding box
        source_crs (QgsCoordinateReferenceSystem): Source CRS
        
    Returns:
        list: [west, south, east, north] in WGS84
    """
    if source_crs.authid() == 'EPSG:4326':
        return [bbox.xMinimum(), bbox.yMinimum(), 
                bbox.xMaximum(), bbox.yMaximum()]
    
    transform = QgsCoordinateTransform(
        source_crs,
        QgsCoordinateReferenceSystem('EPSG:4326'),
        QgsProject.instance()
    )
    
    transformed = transform.transformBoundingBox(bbox)
    return [transformed.xMinimum(), transformed.yMinimum(),
            transformed.xMaximum(), transformed.yMaximum()]


def format_datetime_for_stac(start_date, end_date):
    """Format dates for STAC API
    
    Args:
        start_date (QDate): Start date
        end_date (QDate): End date
        
    Returns:
        str: Formatted datetime string
    """
    start_str = start_date.toString('yyyy-MM-dd')
    end_str = end_date.toString('yyyy-MM-dd')
    return f'{start_str}/{end_str}'
