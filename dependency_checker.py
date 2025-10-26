"""
Dependency checker utility for Open Geodata Browser
"""
from qgis.core import QgsMessageLog, Qgis


class DependencyChecker:
    """Check and report on plugin dependencies"""
    
    REQUIRED_PACKAGES = {
        'open_geodata_api': {
            'name': 'open-geodata-api',
            'version': '1.0.0',
            'install_name': 'open-geodata-api',
            'description': 'Core package for accessing geospatial data APIs'
        }
    }
    
    OPTIONAL_PACKAGES = {
        'geopandas': {
            'name': 'geopandas',
            'version': '0.12.0',
            'install_name': 'geopandas',
            'description': 'Geographic data manipulation'
        },
        'rioxarray': {
            'name': 'rioxarray',
            'version': '0.13.0',
            'install_name': 'rioxarray',
            'description': 'Raster data handling'
        }
    }
    
    @staticmethod
    def check_all_dependencies():
        """Check all required and optional dependencies
        
        Returns:
            dict: Status of all dependencies
        """
        results = {
            'all_required_met': True,
            'required': {},
            'optional': {}
        }
        
        # Check required packages
        for package_import, info in DependencyChecker.REQUIRED_PACKAGES.items():
            is_available = DependencyChecker.check_package(package_import)
            results['required'][package_import] = {
                'available': is_available,
                'info': info
            }
            if not is_available:
                results['all_required_met'] = False
        
        # Check optional packages
        for package_import, info in DependencyChecker.OPTIONAL_PACKAGES.items():
            is_available = DependencyChecker.check_package(package_import)
            results['optional'][package_import] = {
                'available': is_available,
                'info': info
            }
        
        return results
    
    @staticmethod
    def check_package(package_name):
        """Check if a package is available
        
        Args:
            package_name (str): Package name to check
            
        Returns:
            bool: True if package is available
        """
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False
    
    @staticmethod
    def get_install_command(package_import_name):
        """Get pip install command for a package
        
        Args:
            package_import_name (str): Package import name
            
        Returns:
            str: Pip install command
        """
        if package_import_name in DependencyChecker.REQUIRED_PACKAGES:
            install_name = DependencyChecker.REQUIRED_PACKAGES[package_import_name]['install_name']
        elif package_import_name in DependencyChecker.OPTIONAL_PACKAGES:
            install_name = DependencyChecker.OPTIONAL_PACKAGES[package_import_name]['install_name']
        else:
            install_name = package_import_name
        
        return f'python -m pip install {install_name}'
    
    @staticmethod
    def log_dependency_status():
        """Log dependency status to QGIS message log"""
        results = DependencyChecker.check_all_dependencies()
        
        # Log required packages
        QgsMessageLog.logMessage(
            '=== Required Dependencies ===',
            'Open Geodata Browser',
            Qgis.Info
        )
        
        for package, status in results['required'].items():
            status_str = '✓ Available' if status['available'] else '✗ Missing'
            level = Qgis.Info if status['available'] else Qgis.Warning
            
            QgsMessageLog.logMessage(
                f'{package}: {status_str} - {status["info"]["description"]}',
                'Open Geodata Browser',
                level
            )
        
        # Log optional packages
        QgsMessageLog.logMessage(
            '=== Optional Dependencies ===',
            'Open Geodata Browser',
            Qgis.Info
        )
        
        for package, status in results['optional'].items():
            status_str = '✓ Available' if status['available'] else '✗ Missing'
            
            QgsMessageLog.logMessage(
                f'{package}: {status_str} - {status["info"]["description"]}',
                'Open Geodata Browser',
                Qgis.Info
            )
        
        return results
