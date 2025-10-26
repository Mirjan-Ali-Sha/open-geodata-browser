"""
Add/Edit connection dialog - Programmatic UI (No .ui file needed)
"""
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
                                  QLineEdit, QCheckBox, QPushButton, QDialogButtonBox,
                                  QMessageBox, QLabel)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsMessageLog, Qgis


class AddConnectionDialog(QDialog):
    """Dialog for adding/editing STAC API connection"""
    
    def __init__(self, connection=None, parent=None, name=None):
        """Initialize dialog
        
        Args:
            connection (dict): Existing connection config (for editing)
            parent: Parent widget
            name (str): Connection name (for editing)
        """
        super(AddConnectionDialog, self).__init__(parent)
        
        self.connection = connection
        self.connection_name = name
        
        # Setup UI
        self.setWindowTitle('Add STAC API Connection' if not connection else 'Edit STAC API Connection')
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        self.setup_ui()
        
        # Connect signals
        self.testButton.clicked.connect(self.test_connection)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        
        # Load existing connection if editing
        if connection:
            self.load_connection(connection, name)
    
    def setup_ui(self):
        """Setup UI programmatically"""
        layout = QVBoxLayout()
        
        # Form layout
        form_layout = QFormLayout()
        
        # Name
        self.nameEdit = QLineEdit()
        form_layout.addRow('Name:', self.nameEdit)
        
        # URL
        self.urlEdit = QLineEdit()
        self.urlEdit.setPlaceholderText('https://example.com/stac/v1')
        form_layout.addRow('API URL:', self.urlEdit)
        
        # Username
        self.usernameEdit = QLineEdit()
        self.usernameEdit.setPlaceholderText('Optional')
        form_layout.addRow('Username:', self.usernameEdit)
        
        # Password
        self.passwordEdit = QLineEdit()
        self.passwordEdit.setEchoMode(QLineEdit.Password)
        self.passwordEdit.setPlaceholderText('Optional')
        form_layout.addRow('Password:', self.passwordEdit)
        
        # Auto-sign checkbox
        self.autoSignCheck = QCheckBox('Auto-sign URLs (for Planetary Computer)')
        form_layout.addRow('', self.autoSignCheck)
        
        layout.addLayout(form_layout)
        
        # Test button
        self.testButton = QPushButton('Test Connection')
        layout.addWidget(self.testButton)
        
        # Dialog buttons
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        layout.addWidget(self.buttonBox)
        
        self.setLayout(layout)
    
    def load_connection(self, connection, name):
        """Load connection into form"""
        self.nameEdit.setText(name or '')
        self.urlEdit.setText(connection.get('url', ''))
        self.usernameEdit.setText(connection.get('username', ''))
        self.passwordEdit.setText(connection.get('password', ''))
        self.autoSignCheck.setChecked(connection.get('auto_sign', False))
    
    def get_connection_config(self):
        """Get connection configuration from form
        
        Returns:
            dict: Connection configuration
        """
        return {
            'name': self.nameEdit.text().strip(),
            'url': self.urlEdit.text().strip(),
            'username': self.usernameEdit.text().strip(),
            'password': self.passwordEdit.text(),
            'auto_sign': self.autoSignCheck.isChecked()
        }
    
    def test_connection(self):
        """Test the connection"""
        config = self.get_connection_config()
        
        if not config['url']:
            QMessageBox.warning(self, 'Invalid Input', 'Please enter an API URL.')
            return
        
        # Test connection
        from ..core.connection_manager import ConnectionManager
        manager = ConnectionManager()
        
        self.testButton.setEnabled(False)
        self.testButton.setText('Testing...')
        
        success, message = manager.test_connection(config)
        
        self.testButton.setEnabled(True)
        self.testButton.setText('Test Connection')
        
        if success:
            QMessageBox.information(self, 'Connection Successful', message)
        else:
            QMessageBox.critical(self, 'Connection Failed', message)
    
    def accept(self):
        """Validate and accept"""
        config = self.get_connection_config()
        
        if not config['name']:
            QMessageBox.warning(self, 'Invalid Input', 'Please enter a connection name.')
            return
        
        if not config['url']:
            QMessageBox.warning(self, 'Invalid Input', 'Please enter an API URL.')
            return
        
        super().accept()
