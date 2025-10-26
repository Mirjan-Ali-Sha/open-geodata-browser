"""
Main plugin class for Open Geodata Browser
"""
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton, QProgressDialog
from qgis.core import QgsMessageLog, Qgis

from .geodata_browser_dialog import GeodataBrowserDialog


class GeodataBrowser:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        Args:
            iface (QgsInterface): An interface instance that will be passed to this class
                which provides the hook by which you can manipulate the QGIS
                application at run time.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Initialize plugin directory
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GeodataBrowser_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&Open Geodata Browser')
        self.toolbar = self.iface.addToolBar('Open Geodata Browser')
        self.toolbar.setObjectName('OpenGeodataBrowser')
        
        # Plugin dialog
        self.dlg = None
        
        self.log_message("Plugin initialized", Qgis.Info)

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('GeodataBrowser', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar."""

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(self.plugin_dir, 'resources', 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr('Open Geodata Browser'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr('&Open Geodata Browser'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""
        
        # Check dependencies
        if not self.check_dependencies():
            return
        
        # Create the dialog if it doesn't exist
        if self.dlg is None:
            self.dlg = GeodataBrowserDialog(self.iface)
        
        # Show the dialog
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def check_dependencies(self):
        """Check if required Python packages are installed"""
        try:
            import open_geodata_api
            return True
        except ImportError:
            return self.show_dependency_dialog()

    def show_dependency_dialog(self):
        """Show dialog for missing dependencies with installation options"""
        msg_box = QMessageBox(self.iface.mainWindow())
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle('Missing Dependencies')
        msg_box.setText('<b>Open-Geodata-API is not installed.</b>')
        
        install_instructions = """
<p>This plugin requires the <b>open-geodata-api</b> Python package.</p>

<p><b>Installation Methods:</b></p>

<p><b>Method 1: OSGeo4W Shell (Recommended for Windows)</b><br>
1. Close QGIS<br>
2. Open <b>OSGeo4W Shell</b> as Administrator<br>
3. Run: <code>python -m pip install open-geodata-api</code><br>
4. Restart QGIS</p>

<p><b>Method 2: QGIS Python Console</b><br>
1. Open <b>Python Console</b> (Plugins → Python Console)<br>
2. Run the following commands:<br>
<code>import subprocess, sys</code><br>
<code>subprocess.check_call([sys.executable, "-m", "pip", "install", "open-geodata-api"])</code><br>
3. Restart QGIS</p>

<p><b>Method 3: Use Pip Manager Plugin</b><br>
1. Install '<b>Pip Manager</b>' plugin from QGIS Plugin Repository<br>
2. Use it to install '<b>open-geodata-api</b>'<br>
3. Restart QGIS</p>
"""
        
        msg_box.setInformativeText(install_instructions)
        msg_box.setTextFormat(Qt.RichText)
        
        # Add custom buttons
        install_button = msg_box.addButton('Install Now', QMessageBox.ActionRole)
        cancel_button = msg_box.addButton('Cancel', QMessageBox.RejectRole)
        help_button = msg_box.addButton('Copy Install Command', QMessageBox.HelpRole)
        
        msg_box.setDefaultButton(cancel_button)
        
        result = msg_box.exec_()
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == install_button:
            return self.install_dependencies_from_console()
        elif clicked_button == help_button:
            self.copy_install_command()
            QMessageBox.information(
                self.iface.mainWindow(),
                'Command Copied',
                'Installation command copied to clipboard.\n\n'
                'Paste it in OSGeo4W Shell or QGIS Python Console.'
            )
            return False
        
        return False

    def copy_install_command(self):
        """Copy installation command to clipboard"""
        from qgis.PyQt.QtWidgets import QApplication
        command = 'import subprocess, sys\nsubprocess.check_call([sys.executable, "-m", "pip", "install", "open-geodata-api"])'
        QApplication.clipboard().setText(command)

    def install_dependencies_from_console(self):
        """Attempt to install dependencies from within QGIS"""
        try:
            import subprocess
            import sys
            
            # Show progress dialog
            progress = QProgressDialog(
                "Installing open-geodata-api and dependencies...\n\n"
                "This may take several minutes depending on your internet connection.\n"
                "Please do not close QGIS during installation.",
                None, 0, 0, self.iface.mainWindow()
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Installing Dependencies")
            progress.setCancelButton(None)  # Disable cancel
            progress.show()
            
            # Force update the UI
            from qgis.PyQt.QtWidgets import QApplication
            QApplication.processEvents()
            
            self.log_message("Starting installation of open-geodata-api...", Qgis.Info)
            
            # Install package
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "open-geodata-api"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            progress.close()
            
            if result.returncode == 0:
                self.log_message("open-geodata-api installed successfully", Qgis.Success)
                
                QMessageBox.information(
                    self.iface.mainWindow(),
                    'Installation Successful',
                    '<b>open-geodata-api installed successfully!</b><br><br>'
                    'Please <b>restart QGIS</b> for the changes to take effect.<br><br>'
                    'After restarting, you can use the Open Geodata Browser plugin.'
                )
                return False  # Return False to not load plugin yet (needs restart)
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.log_message(f"Installation failed: {error_msg}", Qgis.Critical)
                
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    'Installation Failed',
                    f'<b>Failed to install open-geodata-api</b><br><br>'
                    f'<b>Error:</b><br><code>{error_msg}</code><br><br>'
                    f'<b>Please try manual installation:</b><br>'
                    f'1. Open OSGeo4W Shell as Administrator<br>'
                    f'2. Run: <code>python -m pip install open-geodata-api</code><br>'
                    f'3. Restart QGIS'
                )
                return False
            
        except subprocess.TimeoutExpired:
            if 'progress' in locals():
                progress.close()
            
            QMessageBox.critical(
                self.iface.mainWindow(),
                'Installation Timeout',
                'Installation timed out after 5 minutes.<br><br>'
                'This might be due to slow internet connection.<br><br>'
                'Please try manual installation using OSGeo4W Shell.'
            )
            return False
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            
            self.log_message(f"Installation error: {str(e)}", Qgis.Critical)
            
            QMessageBox.critical(
                self.iface.mainWindow(),
                'Installation Error',
                f'<b>An error occurred during installation:</b><br><br>'
                f'<code>{str(e)}</code><br><br>'
                f'<b>Please try manual installation:</b><br>'
                f'1. Open OSGeo4W Shell as Administrator<br>'
                f'2. Run: <code>python -m pip install open-geodata-api</code><br>'
                f'3. Restart QGIS'
            )
            return False

    def log_message(self, message, level=Qgis.Info):
        """Log message to QGIS message log"""
        QgsMessageLog.logMessage(message, 'Open Geodata Browser', level)
