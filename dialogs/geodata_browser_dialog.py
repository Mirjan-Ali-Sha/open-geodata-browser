# ==========================================
# PART 1 - Imports and Class Init:
# ==========================================
"""
Dialog implementation for Open Geodata Browser with custom connections and map preview
"""
import os
from pathlib import Path
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import (QDialog, QMessageBox, QTableWidgetItem, 
                                  QProgressDialog, QFileDialog, QHeaderView,
                                  QCheckBox, QWidget, QHBoxLayout, QVBoxLayout,
                                  QPushButton, QLineEdit, QLabel, QListWidget,
                                  QTextEdit, QDialogButtonBox, QSplitter)
from qgis.core import (QgsMessageLog, Qgis, QgsRectangle, QgsProject,
                        QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                        QgsGeometry, QgsPointXY, QgsRasterLayer, QgsVectorLayer)
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.PyQt.QtGui import QColor

from ..core.connection_manager import ConnectionManager
from ..core.custom_stac_client import CustomStacClient
from ..utils.layer_loader import LayerLoader
from .connection_dialog import ConnectionDialog

# Load UI file - CORRECTED PATH
current_dir = Path(__file__).parent  # dialogs directory
plugin_dir = current_dir.parent      # plugin root
ui_file = plugin_dir / 'ui' / 'main_dialog.ui'

FORM_CLASS, _ = uic.loadUiType(str(ui_file))



class GeodataBrowserDialog(QDialog, FORM_CLASS):
    """Dialog for browsing and loading geodata with map preview"""
    
    def __init__(self, iface, parent=None):
        """Constructor"""
        super(GeodataBrowserDialog, self).__init__(parent)
        self.setupUi(self)  # THIS MUST BE FIRST!
        
        self.iface = iface
        self.canvas = iface.mapCanvas()
        
        # Initialize components
        self.connection_manager = ConnectionManager()
        self.stac_client = CustomStacClient(self.connection_manager)
        self.layer_loader = LayerLoader(iface)
        
        # Data storage
        self.current_items = []
        self.selected_item = None
        self.selected_items = []
        self.current_item_assets = []
        
        # Map preview components
        self.preview_canvas = None
        self.basemap_layer = None
        self.rubber_bands = []
        self.map_container = None
        self.results_splitter = None
        self.rubber_band = None
        
        # Setup UI - ORDER MATTERS!
        self.setup_ui()
        self.setup_asset_controls()
        self.setup_collection_search()
        self.add_collection_info_button()  # Call AFTER setupUi()
        self.setup_preview_map()
        self.connect_signals()
        
        # Load connections
        self.load_connections()

    # ==========================================
    # PART 2 - Setup Methods:
    # ==========================================

    def add_collection_info_button(self):
        """Add Collection Info button below collection list"""
        search_tab = self.tabWidget.widget(0)
        search_layout = search_tab.layout()
        
        if not search_layout:
            self.log_message('Warning: Could not find search layout', Qgis.Warning)
            return
        
        # Find collection list position in layout
        collection_list_index = -1
        for i in range(search_layout.count()):
            item = search_layout.itemAt(i)
            if item and item.widget() == self.collectionList:
                collection_list_index = i
                self.log_message(f'Found collection list at index {i}', Qgis.Info)
                break
        
        if collection_list_index == -1:
            self.log_message('Warning: Could not find collection list widget', Qgis.Warning)
            return
        
        # Create the button
        self.collectionInfoButton = QPushButton('Collection Info')
        self.collectionInfoButton.setToolTip('View detailed information about selected collection')
        self.collectionInfoButton.setEnabled(False)
        self.collectionInfoButton.setMaximumHeight(30)
        
        # Insert button immediately after collection list
        search_layout.insertWidget(collection_list_index + 1, self.collectionInfoButton)
        
        self.log_message('Collection Info button added successfully', Qgis.Info)

    # PART 3 - Collection Info Methods:
    def on_collection_selection_changed(self):
        """Enable/disable collection info button based on selection"""
        if hasattr(self, 'collectionInfoButton'):
            selected_count = len(self.collectionList.selectedItems())
            self.collectionInfoButton.setEnabled(selected_count == 1)

    def show_collection_info(self):
        """Show detailed information about selected collection"""
        selected_items = self.collectionList.selectedItems()
        
        if not selected_items:
            self.show_warning('Please select a collection first')
            return
        
        if len(selected_items) > 1:
            self.show_warning('Please select only one collection at a time')
            return
        
        collection_id = selected_items[0].text()
        connection_name = self.providerCombo.currentText()
        
        if not connection_name:
            self.show_warning('No provider selected')
            return
        
        connection = self.connection_manager.get_connection(connection_name)
        
        if not connection:
            self.show_warning('Invalid connection')
            return
        
        try:
            self.statusLabel.setText(f'Fetching collection info for {collection_id}...')
            from qgis.PyQt.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            
            collection_info = self.stac_client.get_collection_info(connection, collection_id)
            self.display_collection_info_dialog(collection_id, collection_info)
            self.statusLabel.setText('Ready')
            
        except Exception as e:
            self.show_error(f'Failed to get collection info: {str(e)}')
            self.statusLabel.setText('Ready')

    def display_collection_info_dialog(self, collection_id, info):
        """Display collection information in a dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f'Collection Info: {collection_id}')
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        html_content = self.format_collection_info_html(collection_id, info)
        text_edit.setHtml(html_content)
        
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox()
        copy_button = button_box.addButton('Copy to Clipboard', QDialogButtonBox.ActionRole)
        close_button = button_box.addButton(QDialogButtonBox.Close)
        
        copy_button.clicked.connect(lambda: self.copy_to_clipboard(text_edit.toPlainText()))
        close_button.clicked.connect(dialog.close)
        
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        dialog.exec_()

    def format_collection_info_html(self, collection_id, info):
        """Format collection info as HTML"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 10px; }}
                h2 {{ color: #2c5aa0; border-bottom: 2px solid #2c5aa0; padding-bottom: 5px; }}
                h3 {{ color: #555; margin-top: 15px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f0f0f0; font-weight: bold; }}
                .section {{ margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <h2>Collection: {collection_id}</h2>
            
            <div class="section">
                <h3>Basic Information</h3>
                <table>
                    <tr><th>Property</th><th>Value</th></tr>
                    <tr><td>ID</td><td>{info.get('id', 'N/A')}</td></tr>
                    <tr><td>Title</td><td>{info.get('title', 'N/A')}</td></tr>
                    <tr><td>Description</td><td>{info.get('description', 'N/A')}</td></tr>
                    <tr><td>License</td><td>{info.get('license', 'N/A')}</td></tr>
                </table>
            </div>
        """
        
        # Spatial extent
        if 'extent' in info and 'spatial' in info['extent']:
            spatial = info['extent']['spatial']
            bbox = spatial.get('bbox', [[]])
            if bbox and len(bbox[0]) >= 4:
                html += f"""
            <div class="section">
                <h3>Spatial Extent</h3>
                <table>
                    <tr><th>Coordinate</th><th>Value</th></tr>
                    <tr><td>West</td><td>{bbox[0][0]}</td></tr>
                    <tr><td>South</td><td>{bbox[0][1]}</td></tr>
                    <tr><td>East</td><td>{bbox[0][2]}</td></tr>
                    <tr><td>North</td><td>{bbox[0][3]}</td></tr>
                </table>
            </div>
                """
        
        # Temporal extent
        if 'extent' in info and 'temporal' in info['extent']:
            temporal = info['extent']['temporal']
            interval = temporal.get('interval', [[]])
            if interval and len(interval[0]) >= 2:
                html += f"""
            <div class="section">
                <h3>Temporal Extent</h3>
                <table>
                    <tr><th>Period</th><th>Date</th></tr>
                    <tr><td>Start</td><td>{interval[0][0] or 'Open'}</td></tr>
                    <tr><td>End</td><td>{interval[0][1] or 'Open'}</td></tr>
                </table>
            </div>
                """
        
        # Links
        if 'links' in info and info['links']:
            html += """
            <div class="section">
                <h3>Links</h3>
                <table>
                    <tr><th>Relation</th><th>Type</th><th>URL</th></tr>
            """
            for link in info['links'][:10]:
                rel = link.get('rel', 'N/A')
                type_val = link.get('type', 'N/A')
                href = link.get('href', 'N/A')
                href_display = href[:80] + '...' if len(href) > 80 else href
                html += f"<tr><td>{rel}</td><td>{type_val}</td><td>{href_display}</td></tr>"
            html += "</table></div>"
        
        # Summaries
        if 'summaries' in info and info['summaries']:
            html += """
            <div class="section">
                <h3>Summaries</h3>
                <table>
                    <tr><th>Property</th><th>Value</th></tr>
            """
            count = 0
            for key, value in info['summaries'].items():
                if count >= 15:
                    break
                value_str = str(value)
                value_display = value_str[:100] + '...' if len(value_str) > 100 else value_str
                html += f"<tr><td>{key}</td><td>{value_display}</td></tr>"
                count += 1
            html += "</table></div>"
        
        html += "</body></html>"
        return html

    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        from qgis.PyQt.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.statusLabel.setText('Collection info copied to clipboard')

    # ==========================================
    # PART 4 - ALL CORE SETUP AND UI METHODS
    # ==========================================

    def setup_ui(self):
        """Setup UI components"""
        today = QDate.currentDate()
        self.startDateEdit.setDate(today.addMonths(-3))
        self.endDateEdit.setDate(today)
        
        self.resultsTable.setColumnCount(8)
        self.resultsTable.setHorizontalHeaderLabels([
            'ID', 'Collection', 'Date', 'Cloud Cover %', 
            'Platform', 'Provider', 'Assets', 'Geometry'
        ])
        self.resultsTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        self.assetsTable.setColumnCount(6)
        self.assetsTable.setHorizontalHeaderLabels([
            'Select', 'ID', 'Asset Name', 'Type', 'Size', 'Extension'
        ])
        header = self.assetsTable.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        
        self.cloudCoverSlider.setRange(0, 100)
        self.cloudCoverSlider.setValue(30)
        self.cloudCoverLabel.setText('30%')
        
        self.limitSpinBox.setValue(50)
        self.limitSpinBox.setRange(1, 500)
        
        self.downloadPathEdit.setText(os.path.expanduser('~'))
        
        self.add_extent_buttons()

    def setup_asset_controls(self):
        """Setup Select All/Unselect All controls in Assets tab"""
        assets_tab = self.tabWidget.widget(2)
        layout = assets_tab.layout()
        if not layout:
            layout = QVBoxLayout(assets_tab)
        
        control_container = QWidget()
        control_layout = QHBoxLayout(control_container)
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_layout.setSpacing(10)
        
        self.selectAllButton = QPushButton('Select All')
        self.selectAllButton.clicked.connect(self.select_all_assets)
        control_layout.addWidget(self.selectAllButton)
        
        self.unselectAllButton = QPushButton('Unselect All')
        self.unselectAllButton.clicked.connect(self.unselect_all_assets)
        control_layout.addWidget(self.unselectAllButton)
        
        control_layout.addStretch()
        
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget and hasattr(widget, 'text') and 'Item ID' in widget.text():
                layout.insertWidget(i + 1, control_container)
                break

    def select_all_assets(self):
        """Select all visible assets"""
        count = 0
        for row in range(self.assetsTable.rowCount()):
            if not self.assetsTable.isRowHidden(row):
                checkbox_widget = self.assetsTable.cellWidget(row, 0)
                if checkbox_widget:
                    checkbox = checkbox_widget.findChild(QCheckBox)
                    if checkbox:
                        checkbox.setChecked(True)
                        count += 1
        self.log_message(f'Selected {count} assets', Qgis.Info)

    def unselect_all_assets(self):
        """Unselect all assets"""
        count = 0
        for row in range(self.assetsTable.rowCount()):
            checkbox_widget = self.assetsTable.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)
                    count += 1
        self.log_message(f'Unselected {count} assets', Qgis.Info)

    def setup_collection_search(self):
        """Setup collection search/filter box"""
        search_tab = self.tabWidget.widget(0)
        
        for i in range(search_tab.layout().count()):
            item = search_tab.layout().itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, QLabel) and 'Collection' in widget.text():
                    parent_layout = search_tab.layout()
                    
                    search_container = QWidget()
                    search_layout = QHBoxLayout(search_container)
                    search_layout.setContentsMargins(0, 0, 0, 0)
                    search_layout.setSpacing(10)
                    
                    collections_label = QLabel('Collections:')
                    search_layout.addWidget(collections_label)
                    
                    self.collectionSearchEdit = QLineEdit()
                    self.collectionSearchEdit.setPlaceholderText('Search collections...')
                    self.collectionSearchEdit.setMaximumWidth(200)
                    search_layout.addWidget(self.collectionSearchEdit)
                    
                    search_layout.addStretch()
                    
                    parent_layout.removeWidget(widget)
                    widget.deleteLater()
                    parent_layout.insertWidget(i, search_container)
                    break

    def setup_preview_map(self):
        """Setup map preview canvas with resizable splitter"""
        results_tab = self.tabWidget.widget(1)
        layout = results_tab.layout()
        if not layout:
            layout = QVBoxLayout(results_tab)
        
        if layout.indexOf(self.resultsTable) >= 0:
            layout.removeWidget(self.resultsTable)
        
        load_button_index = layout.indexOf(self.loadSelectedButton)
        if load_button_index >= 0:
            layout.removeWidget(self.loadSelectedButton)
        
        self.results_splitter = QSplitter(Qt.Vertical)
        self.results_splitter.addWidget(self.resultsTable)
        
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        
        self.showMapCheck = QCheckBox('Show Item Footprints on Map')
        self.showMapCheck.setChecked(False)
        map_layout.addWidget(self.showMapCheck)
        
        self.preview_canvas = QgsMapCanvas()
        self.preview_canvas.setCanvasColor(QColor(255, 255, 255))
        self.preview_canvas.setMinimumHeight(200)
        self.preview_canvas.setVisible(False)
        map_layout.addWidget(self.preview_canvas)
        
        self.map_container = map_container
        self.results_splitter.addWidget(map_container)
        
        self.results_splitter.setSizes([900, 100])
        self.results_splitter.setStretchFactor(0, 9)
        self.results_splitter.setStretchFactor(1, 1)
        
        layout.addWidget(self.results_splitter)
        layout.addWidget(self.loadSelectedButton)
        
        self.add_basemap()

    def add_basemap(self):
        """Add Google Satellite basemap"""
        try:
            url = "type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D{x}%26y%3D{y}%26z%3D{z}&zmax=19&zmin=0"
            self.basemap_layer = QgsRasterLayer(url, 'Google Satellite', 'wms')
            
            if self.basemap_layer.isValid():
                self.preview_canvas.setLayers([self.basemap_layer])
                self.preview_canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
                self.log_message('Google Satellite basemap loaded', Qgis.Info)
            else:
                url_osm = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
                self.basemap_layer = QgsRasterLayer(url_osm, 'OpenStreetMap', 'wms')
                if self.basemap_layer.isValid():
                    self.preview_canvas.setLayers([self.basemap_layer])
                    self.preview_canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
                    self.log_message('Fallback to OpenStreetMap', Qgis.Info)
        except Exception as e:
            self.log_message(f'Error loading basemap: {str(e)}', Qgis.Warning)

    def add_extent_buttons(self):
        """Add extent buttons to Search tab"""
        search_tab = self.tabWidget.widget(0)
        search_layout = search_tab.layout()
        
        for i in range(search_layout.count()):
            item = search_layout.itemAt(i)
            if item and item.layout():
                widget_layout = item.layout()
                
                for j in range(widget_layout.count()):
                    widget = widget_layout.itemAt(j).widget()
                    if widget and isinstance(widget, QPushButton) and 'Map Extent' in widget.text():
                        self.layerExtentButton = QPushButton('Layer Extent')
                        self.layerExtentButton.setToolTip('Get extent from selected QGIS layer')
                        widget_layout.insertWidget(widget_layout.indexOf(widget) + 1, self.layerExtentButton)
                        
                        self.fileExtentButton = QPushButton('File Extent')
                        self.fileExtentButton.setToolTip('Get extent from file (shapefile, raster, etc.)')
                        widget_layout.insertWidget(widget_layout.indexOf(self.layerExtentButton) + 1, self.fileExtentButton)
                        
                        self.worldExtentButton = QPushButton('World Extent')
                        self.worldExtentButton.setToolTip('Use global extent (-180, -90, 180, 90)')
                        widget_layout.insertWidget(widget_layout.indexOf(self.fileExtentButton) + 1, self.worldExtentButton)
                        
                        return

    def use_canvas_extent(self):
        """Use current map canvas extent"""
        try:
            extent = self.canvas.extent()
            crs = self.canvas.mapSettings().destinationCrs()
            
            if crs.authid() != 'EPSG:4326':
                transform = QgsCoordinateTransform(
                    crs,
                    QgsCoordinateReferenceSystem('EPSG:4326'),
                    QgsProject.instance()
                )
                extent = transform.transformBoundingBox(extent)
            
            self.bboxWestEdit.setText(f'{extent.xMinimum():.6f}')
            self.bboxSouthEdit.setText(f'{extent.yMinimum():.6f}')
            self.bboxEastEdit.setText(f'{extent.xMaximum():.6f}')
            self.bboxNorthEdit.setText(f'{extent.yMaximum():.6f}')
            
            self.visualize_bbox()
            self.statusLabel.setText('Using map extent')
        except Exception as e:
            self.show_error(f'Failed to get map extent: {str(e)}')

    def clear_bbox(self):
        """Clear bounding box inputs"""
        self.bboxWestEdit.clear()
        self.bboxSouthEdit.clear()
        self.bboxEastEdit.clear()
        self.bboxNorthEdit.clear()
        
        # Remove rubber band
        if self.rubber_band:
            self.rubber_band.reset()
            self.canvas.scene().removeItem(self.rubber_band)
            self.rubber_band = None
            self.canvas.refresh()
        
        self.statusLabel.setText('Bounding box cleared')


    def closeEvent(self, event):
        """Handle dialog close event - cleanup rubber bands"""
        self.cleanup_rubber_bands()
        event.accept()

    def cleanup_rubber_bands(self):
        """Remove all rubber bands from canvas"""
        # Clean bbox rubber band
        if self.rubber_band:
            self.rubber_band.reset()
            self.canvas.scene().removeItem(self.rubber_band)
            self.rubber_band = None
        
        # Clean footprint rubber bands
        for rb in self.rubber_bands:
            rb.reset()
            self.canvas.scene().removeItem(rb)
        self.rubber_bands = []
        
        # Refresh canvas
        self.canvas.refresh()
        
        self.log_message('Cleaned up rubber bands', Qgis.Info)

    def reject(self):
        """Handle dialog rejection (Cancel/X button)"""
        self.cleanup_rubber_bands()
        super().reject()

    def accept(self):
        """Handle dialog acceptance (OK/Close button)"""
        self.cleanup_rubber_bands()
        super().accept()

    def visualize_bbox(self):
        """Visualize bounding box on map canvas"""
        try:
            west = float(self.bboxWestEdit.text())
            south = float(self.bboxSouthEdit.text())
            east = float(self.bboxEastEdit.text())
            north = float(self.bboxNorthEdit.text())
            
            if not self.rubber_band:
                self.rubber_band = QgsRubberBand(self.canvas, True)
            
            self.rubber_band.reset(True)
            self.rubber_band.setColor(QColor(255, 0, 0, 100))
            self.rubber_band.setWidth(2)
            
            rect = QgsRectangle(west, south, east, north)
            
            source_crs = QgsCoordinateReferenceSystem('EPSG:4326')
            dest_crs = self.canvas.mapSettings().destinationCrs()
            
            if source_crs != dest_crs:
                transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
                rect = transform.transformBoundingBox(rect)
            
            self.rubber_band.setToGeometry(QgsGeometry.fromRect(rect), None)
            self.canvas.setExtent(rect)
            self.canvas.refresh()
            
        except ValueError:
            pass
        except Exception as e:
            self.log_message(f'Error visualizing bbox: {str(e)}', Qgis.Warning)

    def validate_search_params(self):
        """Validate search parameters"""
        west = self.bboxWestEdit.text().strip()
        south = self.bboxSouthEdit.text().strip()
        east = self.bboxEastEdit.text().strip()
        north = self.bboxNorthEdit.text().strip()
        
        if not west and not south and not east and not north:
            self.use_world_extent()
            return True
        
        try:
            float(west)
            float(south)
            float(east)
            float(north)
            return True
        except ValueError:
            self.show_warning('Please provide valid bounding box coordinates or leave all fields empty for world search')
            return False

    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    def perform_search(self):
        """Perform STAC search"""
        if not self.validate_search_params():
            return
        
        selected_collections = [item.text() for item in self.collectionList.selectedItems()]
        
        if not selected_collections:
            self.show_warning('Please select at least one collection')
            return
        
        connection_name = self.providerCombo.currentText()
        if not connection_name:
            self.show_warning('Please select a provider')
            return
        
        connection = self.connection_manager.get_connection(connection_name)
        if not connection:
            self.show_warning('Invalid connection')
            return
        
        try:
            bbox = [
                float(self.bboxWestEdit.text()),
                float(self.bboxSouthEdit.text()),
                float(self.bboxEastEdit.text()),
                float(self.bboxNorthEdit.text())
            ]
            
            start_date = self.startDateEdit.date().toString('yyyy-MM-dd')
            end_date = self.endDateEdit.date().toString('yyyy-MM-dd')
            cloud_cover = self.cloudCoverSlider.value()
            limit = self.limitSpinBox.value()
            
            progress = QProgressDialog('Searching...', 'Cancel', 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            from qgis.PyQt.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            
            results = self.stac_client.search_items(
                connection, selected_collections, bbox,
                start_date, end_date, cloud_cover, limit
            )
            
            progress.close()
            
            self.current_items = results
            self.display_search_results(results)
            
            self.tabWidget.setCurrentIndex(1)
            self.statusLabel.setText(f'Found {len(results)} items')
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            self.show_error(f'Search failed: {str(e)}')
            self.statusLabel.setText('Search failed')

    def display_search_results(self, items):
        """Display search results in table"""
        self.resultsTable.setRowCount(0)
        
        for item in items:
            row = self.resultsTable.rowCount()
            self.resultsTable.insertRow(row)
            
            # Item ID
            self.resultsTable.setItem(row, 0, QTableWidgetItem(item.id))
            
            # Collection - use 'collection' not 'collection_id'
            collection = getattr(item, 'collection', 'N/A')
            self.resultsTable.setItem(row, 1, QTableWidgetItem(collection))
            
            # Date - use properties['datetime']
            datetime_str = 'N/A'
            if hasattr(item, 'properties') and item.properties:
                datetime_val = item.properties.get('datetime')
                if datetime_val:
                    try:
                        from datetime import datetime
                        if isinstance(datetime_val, str):
                            dt = datetime.fromisoformat(datetime_val.replace('Z', '+00:00'))
                            datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            datetime_str = str(datetime_val)
                    except:
                        datetime_str = str(datetime_val)
            self.resultsTable.setItem(row, 2, QTableWidgetItem(datetime_str))
            
            # Cloud Cover
            cloud_cover = 'N/A'
            if hasattr(item, 'properties') and item.properties:
                cloud_cover = item.properties.get('eo:cloud_cover', 'N/A')
                if cloud_cover != 'N/A':
                    cloud_cover = f"{cloud_cover:.1f}"
            self.resultsTable.setItem(row, 3, QTableWidgetItem(str(cloud_cover)))
            
            # Platform
            platform = 'N/A'
            if hasattr(item, 'properties') and item.properties:
                platform = item.properties.get('platform', 'N/A')
            self.resultsTable.setItem(row, 4, QTableWidgetItem(platform))
            
            # Provider
            provider = getattr(item, 'provider', 'N/A')
            self.resultsTable.setItem(row, 5, QTableWidgetItem(provider))
            
            # Asset count
            asset_count = len(item.assets) if hasattr(item, 'assets') else 0
            self.resultsTable.setItem(row, 6, QTableWidgetItem(str(asset_count)))
            
            # Geometry type
            geom_type = 'N/A'
            if hasattr(item, 'geometry') and item.geometry:
                geom_type = item.geometry.get('type', 'N/A')
            self.resultsTable.setItem(row, 7, QTableWidgetItem(geom_type))

    def on_item_selection_changed(self):
        """Handle result table selection change"""
        selected_items = self.resultsTable.selectionModel().selectedRows()
        
        if self.showMapCheck.isChecked() and selected_items:
            self.highlight_selected_footprints()

    def load_selected_item(self):
        """Load selected items' assets to Assets tab"""
        selected_items = self.resultsTable.selectionModel().selectedRows()
        
        if not selected_items:
            self.show_warning('Please select at least one item from the results')
            return
        
        selected_rows = sorted(set(item.row() for item in selected_items))
        
        if not selected_rows:
            return
        
        selected_item_objects = []
        for row in selected_rows:
            if 0 <= row < len(self.current_items):
                selected_item_objects.append(self.current_items[row])
        
        if not selected_item_objects:
            return
        
        self.selected_items = selected_item_objects
        
        self.tabWidget.setCurrentIndex(2)
        
        self.itemIdLabel.setText(f'Loading assets from {len(selected_item_objects)} item(s)...')
        
        from qgis.PyQt.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        
        self.display_multiple_items_assets(selected_item_objects)
        
        self.log_message(f'Loaded assets from {len(selected_item_objects)} item(s)', Qgis.Info)

    def extract_extension(self, asset, asset_key, href):
        """Smart extension extraction from multiple sources"""
        extension = None
        
        # Method 1: From href URL
        if href:
            # Remove query parameters first
            clean_url = href.split('?')[0]
            ext = os.path.splitext(clean_url)[1]
            if ext and len(ext) <= 10:  # Reasonable extension length
                extension = ext.lower()
        
        # Method 2: From asset type (MIME type)
        if not extension or extension == '':
            asset_type = asset.type if hasattr(asset, 'type') else ''
            if asset_type:
                # Map MIME types to extensions
                mime_to_ext = {
                    'image/tiff': '.tif',
                    'image/tiff; application=geotiff': '.tif',
                    'image/tiff; application=geotiff; profile=cloud-optimized': '.tif',
                    'image/jp2': '.jp2',
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'application/json': '.json',
                    'application/geo+json': '.geojson',
                    'application/xml': '.xml',
                    'text/xml': '.xml',
                    'application/x-hdf': '.hdf',
                    'application/x-hdf5': '.h5',
                    'application/x-netcdf': '.nc',
                    'application/geopackage+sqlite3': '.gpkg',
                }
                for mime, ext in mime_to_ext.items():
                    if mime.lower() in asset_type.lower():
                        extension = ext
                        break
        
        # Method 3: From asset key (common naming patterns)
        if not extension or extension == '':
            key_lower = asset_key.lower()
            if 'tif' in key_lower or 'geotiff' in key_lower:
                extension = '.tif'
            elif 'jp2' in key_lower or 'jpeg2000' in key_lower:
                extension = '.jp2'
            elif 'jpg' in key_lower or 'jpeg' in key_lower:
                extension = '.jpg'
            elif 'png' in key_lower:
                extension = '.png'
            elif 'json' in key_lower:
                extension = '.json'
            elif 'xml' in key_lower:
                extension = '.xml'
            elif 'safe' in key_lower:
                extension = '.safe'
            elif 'hdf' in key_lower:
                extension = '.hdf'
            elif 'nc' in key_lower or 'netcdf' in key_lower:
                extension = '.nc'
        
        return extension if extension else 'N/A'

    def display_multiple_items_assets(self, items):
        """Display assets for multiple selected items with Item ID grouping"""
        self.assetsTable.setRowCount(0)
        self.current_item_assets = []
        
        # Update label
        if len(items) == 1:
            self.itemIdLabel.setText(f'Item ID: {items[0].id}')
        else:
            self.itemIdLabel.setText(f'Selected Items: {len(items)} items')
        
        # Process each item
        for item in items:
            if not hasattr(item, 'assets'):
                continue
            
            # Iterate through assets
            for asset_key, asset in item.assets.items():
                # Get href
                href = asset.href if hasattr(asset, 'href') else ''
                
                # SMART EXTENSION DETECTION
                extension = self.extract_extension(asset, asset_key, href)
                
                self.current_item_assets.append({
                    'key': asset_key,
                    'asset': asset,
                    'extension': extension,
                    'item': item
                })
                
                row = self.assetsTable.rowCount()
                self.assetsTable.insertRow(row)
                
                # Column 0: Checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(True)
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.assetsTable.setCellWidget(row, 0, checkbox_widget)
                
                # Column 1: Item ID
                id_item = QTableWidgetItem(item.id)
                id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
                self.assetsTable.setItem(row, 1, id_item)
                
                # Column 2: Asset Name
                self.assetsTable.setItem(row, 2, QTableWidgetItem(asset_key))
                
                # Column 3: Type - use asset.type
                asset_type = asset.type if hasattr(asset, 'type') else 'N/A'
                if not asset_type or asset_type == '':
                    asset_type = 'N/A'
                self.assetsTable.setItem(row, 3, QTableWidgetItem(asset_type))
                
                # Column 4: Size - Try multiple approaches
                size = 'N/A'
                size_bytes = None
                
                # Try to get size from asset data
                if hasattr(asset, '_data') and asset._data:
                    # Check common size fields
                    for size_field in ['file:size', 'proj:size', 'size', 'content_length', 'length']:
                        if size_field in asset._data:
                            size_bytes = asset._data.get(size_field)
                            if size_bytes:
                                break
                
                # Format size if found
                if size_bytes is not None:
                    try:
                        size_bytes = int(size_bytes)
                        size = self.format_file_size(size_bytes)
                    except (ValueError, TypeError):
                        size = 'N/A'
                
                self.assetsTable.setItem(row, 4, QTableWidgetItem(size))
                
                # Column 5: Extension (cleaned and smart-detected)
                self.assetsTable.setItem(row, 5, QTableWidgetItem(extension))
        
        # Apply filter
        self.filter_assets_by_type()
        
        # Log success
        total_assets = self.assetsTable.rowCount()
        self.log_message(f'Loaded {total_assets} assets from {len(items)} item(s)', Qgis.Info)

    def load_selected_assets(self):
        """Load selected assets to QGIS"""
        selected_assets = []
        
        for row in range(self.assetsTable.rowCount()):
            if self.assetsTable.isRowHidden(row):
                continue
            
            checkbox_widget = self.assetsTable.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.current_item_assets):
                        selected_assets.append(self.current_item_assets[row])
        
        if not selected_assets:
            self.show_warning('Please select at least one asset to load')
            return
        
        try:
            progress = QProgressDialog('Loading assets...', 'Cancel', 0, len(selected_assets), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            loaded_count = 0
            for i, asset_data in enumerate(selected_assets):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f'Loading {asset_data["key"]}...')
                
                from qgis.PyQt.QtCore import QCoreApplication
                QCoreApplication.processEvents()
                
                # Load asset directly
                asset = asset_data['asset']
                asset_key = asset_data['key']
                item_id = asset_data['item'].id
                
                # Get href
                href = asset.href if hasattr(asset, 'href') else None
                
                if not href:
                    self.log_message(f'No href for asset {asset_key}', Qgis.Warning)
                    continue
                
                # Determine layer type from extension or MIME type
                extension = asset_data['extension'].lower() if asset_data['extension'] != 'N/A' else ''
                asset_type = asset.type if hasattr(asset, 'type') else ''
                
                # Load raster formats
                if any(ext in extension for ext in ['.tif', '.tiff', '.jp2', '.png', '.jpg', '.jpeg']):
                    layer_name = f"{item_id}_{asset_key}"
                    layer = QgsRasterLayer(href, layer_name, 'gdal')
                    
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        loaded_count += 1
                        self.log_message(f'Loaded raster: {layer_name}', Qgis.Success)
                    else:
                        self.log_message(f'Failed to load raster: {layer_name}', Qgis.Warning)
                
                # Load vector formats
                elif any(ext in extension for ext in ['.json', '.geojson', '.gpkg', '.shp']):
                    layer_name = f"{item_id}_{asset_key}"
                    layer = QgsVectorLayer(href, layer_name, 'ogr')
                    
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        loaded_count += 1
                        self.log_message(f'Loaded vector: {layer_name}', Qgis.Success)
                    else:
                        self.log_message(f'Failed to load vector: {layer_name}', Qgis.Warning)
                
                else:
                    self.log_message(f'Unsupported format for {asset_key}: {extension}', Qgis.Info)
            
            progress.close()
            
            if loaded_count > 0:
                self.show_info(f'Successfully loaded {loaded_count} asset(s) to QGIS')
            else:
                self.show_warning('No assets were loaded. Check the format compatibility.')
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            self.show_error(f'Failed to load assets: {str(e)}')

    def download_assets(self):
        """Download selected assets"""
        self._download_assets_internal(structured=False)

    def download_assets_structured(self):
        """Download selected assets in structured format"""
        self._download_assets_internal(structured=True)

    def _download_assets_internal(self, structured=False):
        """Internal method to download assets"""
        selected_assets = []
        
        for row in range(self.assetsTable.rowCount()):
            if self.assetsTable.isRowHidden(row):
                continue
            
            checkbox_widget = self.assetsTable.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.current_item_assets):
                        selected_assets.append(self.current_item_assets[row])
        
        if not selected_assets:
            self.show_warning('Please select at least one asset to download')
            return
        
        download_path = self.downloadPathEdit.text()
        if not download_path:
            self.show_warning('Please specify download path')
            return
        
        try:
            import requests
            
            progress = QProgressDialog('Downloading...', 'Cancel', 0, len(selected_assets), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            downloaded_count = 0
            for i, asset_data in enumerate(selected_assets):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f'Downloading {asset_data["key"]}...')
                
                from qgis.PyQt.QtCore import QCoreApplication
                QCoreApplication.processEvents()
                
                if structured:
                    item_folder = os.path.join(download_path, asset_data['item'].id)
                    os.makedirs(item_folder, exist_ok=True)
                    filename = f"{asset_data['key']}{asset_data['extension']}"
                    filepath = os.path.join(item_folder, filename)
                else:
                    filename = f"{asset_data['item'].id}_{asset_data['key']}{asset_data['extension']}"
                    filepath = os.path.join(download_path, filename)
                
                href = asset_data['asset'].href
                response = requests.get(href, stream=True)
                response.raise_for_status()
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                downloaded_count += 1
            
            progress.close()
            self.show_info(f'Successfully downloaded {downloaded_count} asset(s)')
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            self.show_error(f'Download failed: {str(e)}')

    def browse_download_path(self):
        """Browse for download directory"""
        path = QFileDialog.getExistingDirectory(self, 'Select Download Directory')
        if path:
            self.downloadPathEdit.setText(path)
    def display_footprints(self):
        """Display all item footprints on map"""
        for rb in self.rubber_bands:
            rb.reset()
        self.rubber_bands = []
        
        if not self.current_items:
            return
        
        source_crs = QgsCoordinateReferenceSystem('EPSG:4326')
        dest_crs = self.preview_canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        
        all_extents = []
        
        for item in self.current_items:
            if not item.geometry:
                continue
            
            try:
                geom = QgsGeometry.fromWkt(self.geometry_to_wkt(item.geometry))
                if geom.isEmpty():
                    continue
                
                geom.transform(transform)
                
                rb = QgsRubberBand(self.preview_canvas, False)
                rb.setToGeometry(geom, None)
                rb.setColor(QColor(0, 0, 255, 50))
                rb.setWidth(2)
                rb.setLineStyle(Qt.SolidLine)
                
                self.rubber_bands.append(rb)
                all_extents.append(geom.boundingBox())
                
            except Exception as e:
                self.log_message(f'Error displaying footprint: {str(e)}', Qgis.Warning)
        
        if all_extents:
            combined_extent = all_extents[0]
            for extent in all_extents[1:]:
                combined_extent.combineExtentWith(extent)
            
            combined_extent.scale(1.1)
            self.preview_canvas.setExtent(combined_extent)
            self.preview_canvas.refresh()

    def highlight_selected_footprints(self):
        """Highlight selected item footprints"""
        selected_rows = [item.row() for item in self.resultsTable.selectionModel().selectedRows()]
        
        source_crs = QgsCoordinateReferenceSystem('EPSG:4326')
        dest_crs = self.preview_canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        
        for i, rb in enumerate(self.rubber_bands):
            if i < len(self.current_items):
                if i in selected_rows:
                    rb.setColor(QColor(255, 0, 0, 100))
                    rb.setWidth(3)
                else:
                    rb.setColor(QColor(0, 0, 255, 50))
                    rb.setWidth(2)
        
        self.preview_canvas.refresh()

    def geometry_to_wkt(self, geometry):
        """Convert GeoJSON geometry to WKT"""
        if not geometry:
            return None
        
        geom_type = geometry.get('type', '')
        coords = geometry.get('coordinates', [])
        
        if geom_type == 'Point':
            return f"POINT({coords[0]} {coords[1]})"
        
        elif geom_type == 'LineString':
            points = ', '.join([f"{c[0]} {c[1]}" for c in coords])
            return f"LINESTRING({points})"
        
        elif geom_type == 'Polygon':
            rings = []
            for ring in coords:
                points = ', '.join([f"{c[0]} {c[1]}" for c in ring])
                rings.append(f"({points})")
            return f"POLYGON({', '.join(rings)})"
        
        elif geom_type == 'MultiPolygon':
            polygons = []
            for polygon in coords:
                rings = []
                for ring in polygon:
                    points = ', '.join([f"{c[0]} {c[1]}" for c in ring])
                    rings.append(f"({points})")
                polygons.append(f"({', '.join(rings)})")
            return f"MULTIPOLYGON({', '.join(polygons)})"
        
        return None

    def toggle_map_preview(self, state):
        """Toggle map preview visibility"""
        is_visible = state == Qt.Checked
        
        if hasattr(self, 'preview_canvas'):
            self.preview_canvas.setVisible(is_visible)
            
            if is_visible:
                self.results_splitter.setSizes([700, 300])
            else:
                self.results_splitter.setSizes([950, 50])
        
        if is_visible and self.current_items:
            self.display_footprints()
        else:
            for rb in self.rubber_bands:
                rb.reset()
            self.rubber_bands = []

    def filter_collections(self, text):
        """Filter collections by search text"""
        search_text = text.lower().strip()
        
        if not search_text:
            for i in range(self.collectionList.count()):
                self.collectionList.item(i).setHidden(False)
            return
        
        visible_count = 0
        for i in range(self.collectionList.count()):
            item = self.collectionList.item(i)
            item_text = item.text().lower()
            should_show = search_text in item_text
            item.setHidden(not should_show)
            if should_show:
                visible_count += 1
        
        total = self.collectionList.count()
        if visible_count < total:
            self.statusLabel.setText(f'Showing {visible_count} of {total} collections')

    def load_connections(self):
        """Load saved connections into dropdown"""
        self.providerCombo.clear()
        connection_names = self.connection_manager.get_connection_names()
        self.providerCombo.addItems(connection_names)
        if connection_names:
            self.populate_collections()

    def manage_connections(self):
        """Open connection management dialog"""
        dlg = ConnectionDialog(self.connection_manager, self)
        if dlg.exec_():
            self.load_connections()

    def populate_collections(self):
        """Populate collection list based on selected connection"""
        try:
            connection_name = self.providerCombo.currentText()
            if not connection_name:
                return
            
            connection = self.connection_manager.get_connection(connection_name)
            if not connection:
                return
            
            collections = self.stac_client.list_collections(connection)
            self.collectionList.clear()
            self.collectionList.addItems(collections)
            
            if hasattr(self, 'collectionSearchEdit'):
                self.collectionSearchEdit.clear()
            
            self.statusLabel.setText(f'Loaded {len(collections)} collections from {connection_name}')
        except Exception as e:
            self.log_message(f'Error populating collections: {str(e)}', Qgis.Warning)
            self.statusLabel.setText('Error loading collections')

    def on_provider_changed(self, provider_text):
        """Handle provider selection change"""
        self.populate_collections()

    def filter_assets_by_type(self):
        """Filter assets table by selected file type - strict exact matching"""
        filter_text = self.fileTypeCombo.currentText()
        
        if filter_text == 'All':
            for row in range(self.assetsTable.rowCount()):
                self.assetsTable.setRowHidden(row, False)
            return
        
        extensions = []
        if '.jpg / .jpeg' in filter_text or 'JPEG)' in filter_text:
            extensions = ['.jpg', '.jpeg']
        elif '.jp2' in filter_text or 'JPEG2000' in filter_text:
            extensions = ['.jp2']
        elif '.safe' in filter_text or 'SAFE' in filter_text:
            extensions = ['.safe']
        elif '.xml' in filter_text and 'SAFE' not in filter_text:
            extensions = ['.xml']
        elif '.tif / .tiff' in filter_text or 'GeoTIFF' in filter_text:
            extensions = ['.tif', '.tiff']
        elif '.json' in filter_text or 'JSON' in filter_text:
            extensions = ['.json']
        elif '.png' in filter_text or 'PNG' in filter_text:
            extensions = ['.png']
        elif '.h5 / .hdf' in filter_text or 'HDF' in filter_text:
            extensions = ['.h5', '.hdf', '.hdf5']
        elif '.nc' in filter_text or 'NetCDF' in filter_text:
            extensions = ['.nc']
        else:
            parts = filter_text.split()
            if parts:
                ext = parts[0]
                if ext.startswith('.'):
                    extensions = [ext]
        
        visible_count = 0
        for row in range(self.assetsTable.rowCount()):
            ext_item = self.assetsTable.item(row, 5)
            if ext_item:
                ext_text = ext_item.text().lower().strip()
                
                if '?' in ext_text:
                    ext_text = ext_text.split('?')[0]
                
                should_show = ext_text in [e.lower() for e in extensions]
                self.assetsTable.setRowHidden(row, not should_show)
                
                if should_show:
                    visible_count += 1
        
        total = self.assetsTable.rowCount()
        if visible_count < total:
            self.log_message(f'Showing {visible_count} of {total} assets', Qgis.Info)

    def use_layer_extent(self):
        """Get extent from selected QGIS layer"""
        try:
            layer = self.iface.activeLayer()
            
            if not layer:
                self.show_warning('Please select a layer in the Layers panel first')
                return
            
            extent = layer.extent()
            crs = layer.crs()
            
            if crs.authid() != 'EPSG:4326':
                transform = QgsCoordinateTransform(
                    crs,
                    QgsCoordinateReferenceSystem('EPSG:4326'),
                    QgsProject.instance()
                )
                extent = transform.transformBoundingBox(extent)
            
            self.bboxWestEdit.setText(f'{extent.xMinimum():.6f}')
            self.bboxSouthEdit.setText(f'{extent.yMinimum():.6f}')
            self.bboxEastEdit.setText(f'{extent.xMaximum():.6f}')
            self.bboxNorthEdit.setText(f'{extent.yMaximum():.6f}')
            
            self.visualize_bbox()
            self.statusLabel.setText(f'Extent from layer: {layer.name()}')
            
        except Exception as e:
            self.show_error(f'Failed to get layer extent: {str(e)}')

    def use_file_extent(self):
        """Get extent from file"""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, 'Select File for Extent', '',
                'All Supported Files (*.shp *.geojson *.gpkg *.kml *.tif *.tiff *.jp2 *.img);;'
                'Vector Files (*.shp *.geojson *.gpkg *.kml);;'
                'Raster Files (*.tif *.tiff *.jp2 *.img);;All Files (*.*)'
            )
            
            if not filename:
                return
            
            layer = QgsVectorLayer(filename, 'temp', 'ogr')
            if not layer.isValid():
                layer = QgsRasterLayer(filename, 'temp')
            
            if not layer.isValid():
                self.show_error('Cannot read file. Please select a valid vector or raster file.')
                return
            
            extent = layer.extent()
            crs = layer.crs()
            
            if crs.authid() != 'EPSG:4326':
                transform = QgsCoordinateTransform(
                    crs, QgsCoordinateReferenceSystem('EPSG:4326'),
                    QgsProject.instance()
                )
                extent = transform.transformBoundingBox(extent)
            
            self.bboxWestEdit.setText(f'{extent.xMinimum():.6f}')
            self.bboxSouthEdit.setText(f'{extent.yMinimum():.6f}')
            self.bboxEastEdit.setText(f'{extent.xMaximum():.6f}')
            self.bboxNorthEdit.setText(f'{extent.yMaximum():.6f}')
            
            self.visualize_bbox()
            self.statusLabel.setText(f'Extent from file: {os.path.basename(filename)}')
            
        except Exception as e:
            self.show_error(f'Failed to get file extent: {str(e)}')

    def use_world_extent(self):
        """Use world extent for global search"""
        self.bboxWestEdit.setText('-180.0')
        self.bboxSouthEdit.setText('-90.0')
        self.bboxEastEdit.setText('180.0')
        self.bboxNorthEdit.setText('90.0')
        self.visualize_bbox()
        self.statusLabel.setText('Using world extent for global search')

    def log_message(self, message, level=Qgis.Info):
        """Log message to QGIS message log"""
        QgsMessageLog.logMessage(message, 'Open Geodata Browser', level)

    def show_warning(self, message):
        """Show warning message box"""
        QMessageBox.warning(self, 'Warning', message)

    def show_error(self, message):
        """Show error message box"""
        QMessageBox.critical(self, 'Error', message)

    def show_info(self, message):
        """Show info message box"""
        QMessageBox.information(self, 'Information', message)

    # ==========================================
    # PART 5 - Updated connect_signals() method:
    # ==========================================

    def connect_signals(self):
        """Connect UI signals"""
        # Connection management
        self.manageConnectionsButton.clicked.connect(self.manage_connections)
        self.providerCombo.currentTextChanged.connect(self.on_provider_changed)
        
        # Buttons
        self.searchButton.clicked.connect(self.perform_search)
        self.useBBoxButton.clicked.connect(self.use_canvas_extent)
        self.clearBBoxButton.clicked.connect(self.clear_bbox)
        self.loadSelectedButton.clicked.connect(self.load_selected_item)
        self.loadAssetButton.clicked.connect(self.load_selected_assets)
        self.downloadButton.clicked.connect(self.download_assets)
        self.downloadStructuredButton.clicked.connect(self.download_assets_structured)
        self.browseButton.clicked.connect(self.browse_download_path)
        
        # New extent buttons
        if hasattr(self, 'layerExtentButton'):
            self.layerExtentButton.clicked.connect(self.use_layer_extent)
        if hasattr(self, 'fileExtentButton'):
            self.fileExtentButton.clicked.connect(self.use_file_extent)
        if hasattr(self, 'worldExtentButton'):
            self.worldExtentButton.clicked.connect(self.use_world_extent)
        
        # Collection list selection - ADD THIS
        self.collectionList.itemSelectionChanged.connect(self.on_collection_selection_changed)
        
        # Collection info button - ADD THIS
        if hasattr(self, 'collectionInfoButton'):
            self.collectionInfoButton.clicked.connect(self.show_collection_info)
        
        # Table selections
        self.resultsTable.itemSelectionChanged.connect(self.on_item_selection_changed)
        
        # Map preview
        self.showMapCheck.stateChanged.connect(self.toggle_map_preview)
        
        # Filters
        self.fileTypeCombo.currentTextChanged.connect(self.filter_assets_by_type)
        
        # Collection search
        if hasattr(self, 'collectionSearchEdit'):
            self.collectionSearchEdit.textChanged.connect(self.filter_collections)
        
        # Cloud cover slider
        self.cloudCoverSlider.valueChanged.connect(
            lambda v: self.cloudCoverLabel.setText(f'{v}%')
        )
