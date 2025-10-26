"""
Connection management dialog - Programmatic UI (No .ui file needed)
"""
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                                  QListWidget, QGroupBox, QDialogButtonBox, QMessageBox)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsMessageLog, Qgis

from .add_connection_dialog import AddConnectionDialog


class ConnectionDialog(QDialog):
    """Dialog for managing STAC API connections"""
    
    def __init__(self, connection_manager, parent=None):
        """Initialize dialog"""
        super(ConnectionDialog, self).__init__(parent)
        
        self.connection_manager = connection_manager
        
        # Setup UI
        self.setWindowTitle('Manage STAC API Connections')
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Create widgets
        self.setup_ui()
        
        # Connect signals
        self.addButton.clicked.connect(self.add_connection)
        self.editButton.clicked.connect(self.edit_connection)
        self.removeButton.clicked.connect(self.remove_connection)
        self.buttonBox.rejected.connect(self.reject)
        
        # Load connections
        self.load_connections()
    
    def setup_ui(self):
        """Setup UI programmatically"""
        layout = QVBoxLayout()
        
        # Group box
        group = QGroupBox('STAC API Connections')
        group_layout = QVBoxLayout()
        
        # List widget
        self.connectionsList = QListWidget()
        group_layout.addWidget(self.connectionsList)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.addButton = QPushButton('Add')
        self.editButton = QPushButton('Edit')
        self.removeButton = QPushButton('Remove')
        
        button_layout.addWidget(self.addButton)
        button_layout.addWidget(self.editButton)
        button_layout.addWidget(self.removeButton)
        button_layout.addStretch()
        
        group_layout.addLayout(button_layout)
        group.setLayout(group_layout)
        
        layout.addWidget(group)
        
        # Dialog buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close)
        layout.addWidget(self.buttonBox)
        
        self.setLayout(layout)
    
    def load_connections(self):
        """Load connections into list"""
        self.connectionsList.clear()
        connections = self.connection_manager.get_connection_names()
        self.connectionsList.addItems(connections)
    
    def add_connection(self):
        """Add new connection"""
        dlg = AddConnectionDialog(None, self)
        if dlg.exec_():
            config = dlg.get_connection_config()
            name = config['name']
            
            # Check if name exists
            if name in self.connection_manager.get_connection_names():
                QMessageBox.warning(
                    self,
                    'Duplicate Name',
                    f'Connection "{name}" already exists.'
                )
                return
            
            self.connection_manager.save_connection(name, config)
            self.load_connections()
    
    def edit_connection(self):
        """Edit selected connection"""
        current_item = self.connectionsList.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'No Selection', 'Please select a connection to edit.')
            return
        
        name = current_item.text()
        connection = self.connection_manager.get_connection(name)
        
        dlg = AddConnectionDialog(connection, self, name)
        if dlg.exec_():
            config = dlg.get_connection_config()
            new_name = config['name']
            
            # If name changed, delete old and create new
            if new_name != name:
                self.connection_manager.delete_connection(name)
            
            self.connection_manager.save_connection(new_name, config)
            self.load_connections()
    
    def remove_connection(self):
        """Remove selected connection"""
        current_item = self.connectionsList.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'No Selection', 'Please select a connection to remove.')
            return
        
        name = current_item.text()
        
        reply = QMessageBox.question(
            self,
            'Confirm Removal',
            f'Are you sure you want to remove connection "{name}"?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.connection_manager.delete_connection(name)
            self.load_connections()
