"""
Open Geodata Browser - QGIS Plugin
Provides access to satellite imagery from multiple STAC providers
"""
import sys
import os
from pathlib import Path

def setup_dependencies():
    """Setup dependencies - try bundled first, then install if needed"""
    plugin_dir = Path(__file__).parent
    
    # Method 1: Try bundled dependencies
    extlibs_path = plugin_dir / 'extlibs'
    if extlibs_path.exists():
        if str(extlibs_path) not in sys.path:
            sys.path.insert(0, str(extlibs_path))
    
    # Method 2: Check if already installed
    try:
        import open_geodata_api
        return True
    except ImportError:
        pass
    
    # Method 3: Auto-install
    return auto_install_dependencies()

def auto_install_dependencies():
    """Auto-install missing dependencies"""
    try:
        import subprocess
        from qgis.core import QgsMessageLog, Qgis, QgsApplication
        
        QgsMessageLog.logMessage(
            'Installing open-geodata-api and its dependencies...',
            'Open Geodata Browser',
            Qgis.Info
        )
        
        python = sys.executable
        env = os.environ.copy()
        
        # Install to QGIS user directory
        qgis_python_dir = Path(QgsApplication.qgisSettingsDirPath()) / "python"
        env["PYTHONUSERBASE"] = str(qgis_python_dir)
        
        site_packages = qgis_python_dir / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        
        if str(site_packages) not in sys.path:
            sys.path.insert(1, str(site_packages))
        
        # Install open-geodata-api (includes pystac-client automatically)
        result = subprocess.run(
            [python, '-m', 'pip', 'install', '--user', 'open-geodata-api'],
            env=env,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            QgsMessageLog.logMessage(
                'open-geodata-api installed successfully. Please restart QGIS.',
                'Open Geodata Browser',
                Qgis.Success
            )
            return True
        else:
            QgsMessageLog.logMessage(
                f'Installation failed: {result.stderr}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            return False
            
    except Exception as e:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f'Error installing dependencies: {str(e)}',
            'Open Geodata Browser',
            Qgis.Critical
        )
        return False

# Setup dependencies when plugin loads
setup_dependencies()

def classFactory(iface):
    """Load GeodataBrowser class
    
    Args:
        iface (QgsInterface): A QGIS interface instance.
    """
    from .geodata_browser import GeodataBrowser
    return GeodataBrowser(iface)
