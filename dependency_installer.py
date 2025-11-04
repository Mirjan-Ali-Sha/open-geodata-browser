"""
Dependency installer for Open Geodata Browser plugin
Handles package installation without spawning new QGIS instances
"""

import sys
import os
import subprocess
from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QApplication
from qgis.PyQt.QtCore import Qt


class DependencyInstaller:
    """Handle installation of Python dependencies"""
    
    def __init__(self, iface):
        self.iface = iface
        self.required_packages = {
            'open-geodata-api': 'open_geodata_api',
            'pystac-client': 'pystac_client',
            'requests': 'requests'
        }
    
    def check_dependencies(self):
        """Check if all required packages are installed"""
        missing = []
        
        for package_name, import_name in self.required_packages.items():
            try:
                __import__(import_name)
                QgsMessageLog.logMessage(
                    f'✓ {package_name} is installed',
                    'Open Geodata Browser',
                    Qgis.Info
                )
            except ImportError:
                missing.append(package_name)
                QgsMessageLog.logMessage(
                    f'✗ {package_name} is missing',
                    'Open Geodata Browser',
                    Qgis.Warning
                )
        
        return missing
    
    def install_dependencies(self, missing_packages):
        """Install missing packages with proper subprocess handling"""
        
        # Show confirmation dialog
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle('Install Dependencies')
        msg.setText(f'The following packages need to be installed:\n\n' + 
                   '\n'.join(f'• {pkg}' for pkg in missing_packages))
        msg.setInformativeText('This will install packages using pip. Continue?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        
        if msg.exec_() != QMessageBox.Yes:
            return False
        
        # Create progress dialog
        progress = QProgressDialog(
            'Installing dependencies...',
            'Cancel',
            0,
            len(missing_packages),
            self.iface.mainWindow()
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.show()
        
        success_count = 0
        failed_packages = []
        
        for i, package in enumerate(missing_packages):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f'Installing {package}...')
            QApplication.processEvents()
            
            if self.install_package(package):
                success_count += 1
            else:
                failed_packages.append(package)
        
        progress.setValue(len(missing_packages))
        progress.close()
        
        # Show results
        if failed_packages:
            QMessageBox.warning(
                self.iface.mainWindow(),
                'Installation Incomplete',
                f'Successfully installed: {success_count}/{len(missing_packages)}\n\n'
                f'Failed to install:\n' + '\n'.join(f'• {pkg}' for pkg in failed_packages) +
                '\n\nPlease install manually using:\n'
                f'pip install --user {" ".join(failed_packages)}'
            )
            return False
        else:
            QMessageBox.information(
                self.iface.mainWindow(),
                'Installation Complete',
                f'Successfully installed all {success_count} packages!\n\n'
                'Please restart QGIS to use the plugin.'
            )
            return True
    
    def install_package(self, package_name):
        """Install a single package using subprocess correctly"""
        try:
            # Get Python executable from QGIS
            python_exe = sys.executable
            
            QgsMessageLog.logMessage(
                f'Installing {package_name} using {python_exe}',
                'Open Geodata Browser',
                Qgis.Info
            )
            
            # CRITICAL: Pass command as a LIST, not a string
            # This prevents the arguments from being interpreted as file paths
            cmd = [
                python_exe,
                '-m',
                'pip',
                'install',
                '--user',
                '--upgrade',
                package_name
            ]
            
            # Run subprocess with proper settings
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,  # Don't raise exception on non-zero exit
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Check result
            if result.returncode == 0:
                QgsMessageLog.logMessage(
                    f'✓ Successfully installed {package_name}',
                    'Open Geodata Browser',
                    Qgis.Success
                )
                return True
            else:
                QgsMessageLog.logMessage(
                    f'✗ Failed to install {package_name}\n'
                    f'Error: {result.stderr}',
                    'Open Geodata Browser',
                    Qgis.Critical
                )
                return False
                
        except subprocess.TimeoutExpired:
            QgsMessageLog.logMessage(
                f'✗ Installation of {package_name} timed out',
                'Open Geodata Browser',
                Qgis.Critical
            )
            return False
        except Exception as e:
            QgsMessageLog.logMessage(
                f'✗ Error installing {package_name}: {str(e)}',
                'Open Geodata Browser',
                Qgis.Critical
            )
            return False


def check_and_install_dependencies(iface):
    """Main function to check and install dependencies"""
    installer = DependencyInstaller(iface)
    
    # Check for missing packages
    missing = installer.check_dependencies()
    
    if not missing:
        QgsMessageLog.logMessage(
            'All dependencies are installed',
            'Open Geodata Browser',
            Qgis.Success
        )
        return True
    
    # Install missing packages
    return installer.install_dependencies(missing)
