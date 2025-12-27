# -*- coding: utf-8 -*-
"""
Open Geodata Browser
QGIS Plugin for browsing and downloading satellite imagery from STAC APIs
"""

import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QToolBar, QMessageBox
from qgis.core import QgsMessageLog, Qgis

# Flag to track if dependencies are available
DEPENDENCIES_AVAILABLE = False

# Try to import required packages
try:
    import open_geodata_api
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    pass


class GeodataBrowser:
    """QGIS Plugin Implementation for Open Geodata Browser"""
    
    # Required packages: {pip_package_name: import_module_name}
    REQUIRED_PACKAGES = {
        'open-geodata-api': 'open_geodata_api',
    }
    
    def __init__(self, iface):
        """Constructor"""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'GeodataBrowser_{locale}.qm'
        )
        
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
        
        # Instance attributes
        self.actions = []
        self.menu = self.tr(u'MAS Raster Processing')
        self.toolbar = None
        self.dlg = None
        self.action = None
        self.dependencies_ok = DEPENDENCIES_AVAILABLE
    
    def tr(self, message):
        """Get translation"""
        return QCoreApplication.translate('GeodataBrowser', message)
    
    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True, status_tip=None,
                   whats_this=None, parent=None):
        """Add toolbar icon"""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        
        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)
        
        if add_to_toolbar and self.toolbar:
            self.toolbar.addAction(action)
        
        if add_to_menu:
            self.iface.addPluginToRasterMenu(self.menu, action)
        
        self.actions.append(action)
        return action
    
    def initGui(self):
        """Create menu entries and toolbar icons"""
        icon_path = os.path.join(self.plugin_dir, 'resources', 'icon.png')
        
        # Find or create toolbar
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, 'MASRasterProcessingToolbar')
        if self.toolbar is None:
            self.toolbar = self.iface.addToolBar(u'MAS Raster Processing')
            self.toolbar.setObjectName('MASRasterProcessingToolbar')
        
        # Create action
        self.action = self.add_action(
            icon_path,
            text=self.tr(u'Open Geodata Browser'),
            callback=self.run,
            status_tip=self.tr('Browse and download satellite imagery from STAC APIs'),
            whats_this=self.tr('Access satellite imagery from multiple STAC providers'),
            parent=self.iface.mainWindow()
        )
    
    def unload(self):
        """Remove plugin menu and icon"""
        for action in self.actions:
            self.iface.removePluginRasterMenu(self.tr(u'MAS Raster Processing'), action)
            if self.toolbar:
                self.toolbar.removeAction(action)
    
    def run(self):
        """Run plugin"""
        # Check if dependencies are available
        if not self.dependencies_ok:
            # Try to reload dependencies first (they might have been installed)
            if self._reload_dependencies():
                self.dependencies_ok = True
            else:
                # Still not available - prompt for installation
                self._check_and_install_dependencies()
                if not self.dependencies_ok:
                    return
        
        # Create dialog
        if self.dlg is None:
            try:
                from .dialogs.geodata_browser_dialog import GeodataBrowserDialog
                self.dlg = GeodataBrowserDialog(self.iface)
            except ImportError as e:
                self.log_message(f'Failed to import dialog: {str(e)}', Qgis.Critical)
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    'Import Error',
                    f'Failed to load plugin dialog:\n{str(e)}'
                )
                return
        
        # Show dialog
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
    
    def _check_and_install_dependencies(self):
        """Check and install missing dependencies using the robust installer"""
        try:
            from .dependency_installer import DependencyInstaller
            
            installer = DependencyInstaller(self.iface, self.REQUIRED_PACKAGES)
            installer.PLUGIN_NAME = "Open Geodata Browser"
            
            if installer.check_and_install(silent_if_ok=True):
                # Dependencies installed successfully - try to reload them
                if self._reload_dependencies():
                    self.dependencies_ok = True
                    QMessageBox.information(
                        self.iface.mainWindow(),
                        "Ready to Use",
                        "Dependencies installed successfully!\n\n"
                        "The plugin is now ready to use."
                    )
                else:
                    self.dependencies_ok = False
            else:
                self.dependencies_ok = False
        except Exception as e:
            self.log_message(f"Failed to check dependencies: {str(e)}", Qgis.Warning)
            self.dependencies_ok = False
    
    def _reload_dependencies(self):
        """
        Try to reload/import all required dependencies after installation.
        Returns True if all imports succeed, False otherwise.
        """
        global DEPENDENCIES_AVAILABLE
        global open_geodata_api
        
        try:
            import open_geodata_api as _oga
            open_geodata_api = _oga
            
            DEPENDENCIES_AVAILABLE = True
            
            self.log_message("Successfully reloaded all dependencies", Qgis.Success)
            return True
            
        except ImportError as e:
            self.log_message(f"Failed to reload dependencies: {str(e)}", Qgis.Warning)
            return False
    
    def log_message(self, message, level=Qgis.Info):
        """Log message to QGIS"""
        QgsMessageLog.logMessage(message, 'Open Geodata Browser', level)
