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


class GeodataBrowser:
    """QGIS Plugin Implementation for Open Geodata Browser"""
    
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
        self.dependencies_checked = False
        self.dependencies_ok = False
    
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
        # Check dependencies only once
        if not self.dependencies_checked:
            self.log_message('Checking dependencies...', Qgis.Info)
            if not self.check_dependencies():
                self.log_message('Dependencies check failed', Qgis.Warning)
                return
            
            self.dependencies_checked = True
            self.dependencies_ok = True
        
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
    
    def check_dependencies(self):
        """Check if open-geodata-api is installed"""
        try:
            import open_geodata_api
            self.log_message('✓ open-geodata-api is installed', Qgis.Success)
            return True
        except ImportError:
            self.log_message('✗ open-geodata-api is missing', Qgis.Warning)
            return self.show_install_dialog()
    
    def show_install_dialog(self):
        """Show dialog for installing open-geodata-api"""
        msg = QMessageBox(self.iface.mainWindow())
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle('Missing Dependencies')
        msg.setText('Open Geodata API Not Installed')
        
        install_text = """The 'open-geodata-api' package is required but not installed.

This package provides access to satellite imagery from multiple STAC providers.

INSTALLATION INSTRUCTIONS:

Method 1: QGIS Python Console (Recommended)
1. Open Python Console (Plugins → Python Console)
2. Copy and paste:

from pip._internal.main import main as pip_main
pip_main(['install', '--user', '--upgrade', 'open-geodata-api'])

3. Restart QGIS

Method 2: OSGeo4W Shell (Windows)
1. Close QGIS
2. Open OSGeo4W Shell as Administrator
3. Run: python -m pip install --user open-geodata-api
4. Restart QGIS

Method 3: Command Line (Any System)
pip install --user open-geodata-api
"""
        
        msg.setInformativeText(install_text)
        msg.setTextFormat(Qt.PlainText)
        msg.setDetailedText('For more help: https://github.com/Mirjan-Ali-Sha/open-geodata-browser')
        
        # Add buttons
        try_now = msg.addButton('Try Install Now', QMessageBox.ActionRole)
        cancel_btn = msg.addButton('Cancel', QMessageBox.RejectRole)
        msg.setDefaultButton(cancel_btn)
        
        msg.exec_()
        clicked = msg.clickedButton()
        
        if clicked == try_now:
            return self.install_open_geodata_api()
        
        return False
    
    def install_open_geodata_api(self):
        """Install open-geodata-api using subprocess with correct Python path"""
        try:
            import subprocess
            import sys
            import os
            
            # Get QGIS Python executable (not sys.executable which is QGIS binary)
            # Method 1: Try to find python.exe in QGIS bin directory
            python_exe = None
            
            if sys.executable.lower().endswith('qgis-bin.exe'):
                # We're in QGIS, find python.exe in the same directory
                qgis_bin_dir = os.path.dirname(sys.executable)
                python_candidate = os.path.join(qgis_bin_dir, 'python.exe')
                if os.path.exists(python_candidate):
                    python_exe = python_candidate
            
            # Method 2: Fallback to the current Python interpreter module
            if not python_exe:
                python_exe = sys.executable
            
            QMessageBox.information(
                self.iface.mainWindow(),
                'Installing Package',
                f'Installing open-geodata-api...\n\n'
                f'Using Python: {os.path.basename(python_exe)}\n'
                'Please wait...'
            )
            
            # Use the correct Python executable for pip
            result = subprocess.run(
                [python_exe, '-m', 'pip', 'install', '--user', '--upgrade', 'open-geodata-api'],
                capture_output=True,
                text=True,
                timeout=300  # Increased timeout to 5 minutes
            )
            
            if result.returncode == 0:
                self.log_message('✓ Successfully installed open-geodata-api', Qgis.Success)
                QMessageBox.information(
                    self.iface.mainWindow(),
                    'Installation Complete',
                    'Successfully installed open-geodata-api!\n\n'
                    'Please RESTART QGIS to use the plugin.'
                )
                return True
            else:
                error_output = result.stderr[:300] if result.stderr else result.stdout[:300]
                self.log_message(f'✗ Installation failed: {error_output}', Qgis.Critical)
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    'Installation Failed',
                    f'Error:\n{error_output}\n\n'
                    'Try installing manually:\n'
                    'pip install --user open-geodata-api'
                )
                return False
        
        except subprocess.TimeoutExpired:
            self.log_message('✗ Installation timed out', Qgis.Critical)
            QMessageBox.critical(
                self.iface.mainWindow(),
                'Installation Timeout',
                'Installation took too long.\n\n'
                'Install manually using:\n'
                'pip install --user open-geodata-api'
            )
            return False
        
        except Exception as e:
            self.log_message(f'✗ Installation error: {str(e)}', Qgis.Critical)
            QMessageBox.critical(
                self.iface.mainWindow(),
                'Installation Error',
                f'Error: {str(e)}\n\n'
                'Install manually using:\n'
                'pip install --user open-geodata-api'
            )
            return False

    
    def log_message(self, message, level=Qgis.Info):
        """Log message to QGIS"""
        QgsMessageLog.logMessage(message, 'Open Geodata Browser', level)
