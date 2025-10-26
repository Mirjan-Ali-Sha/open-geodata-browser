"""
Dialog implementation for Open Geodata Browser with custom connections and map preview
"""
import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDate, pyqtSignal
from qgis.PyQt.QtWidgets import (QDialog, QMessageBox, QTableWidgetItem, 
                                  QProgressDialog, QFileDialog, QHeaderView,
                                  QCheckBox, QWidget, QHBoxLayout, QVBoxLayout,
                                  QSplitter)
from qgis.core import (QgsMessageLog, Qgis, QgsRectangle, QgsProject,
                        QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                        QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
                        QgsSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer,
                        QgsFillSymbol, QgsLineSymbol, QgsRasterLayer)
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.PyQt.QtGui import QColor

from .core.connection_manager import ConnectionManager
from .core.custom_stac_client import CustomStacClient
from .utils.layer_loader import LayerLoader
from .dialogs.connection_dialog import ConnectionDialog

# Load UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui', 'main_dialog.ui'))


class GeodataBrowserDialog(QDialog, FORM_CLASS):
    """Dialog for browsing and loading geodata with map preview"""
    
    def __init__(self, iface, parent=None):
        """Constructor"""
        super(GeodataBrowserDialog, self).__init__(parent)
        self.setupUi(self)
        
        self.iface = iface
        self.canvas = iface.mapCanvas()
        
        # Initialize components
        self.connection_manager = ConnectionManager()
        self.stac_client = CustomStacClient(self.connection_manager)
        self.layer_loader = LayerLoader(iface)
        
        # Data storage
        self.current_items = []
        self.selected_item = None
        self.current_item_assets = []
        
        # Map preview components
        self.preview_canvas = None
        self.basemap_layer = None
        self.rubber_bands = []
        self.map_container = None
        
        # Rubber band for bbox visualization
        self.rubber_band = None
        
        # Setup UI
        self.setup_ui()
        self.setup_preview_map()
        self.connect_signals()
        
        # Load connections
        self.load_connections()

    def setup_ui(self):
        """Setup UI components"""
        # Set date ranges
        today = QDate.currentDate()
        self.startDateEdit.setDate(today.addMonths(-3))
        self.endDateEdit.setDate(today)
        
        # Setup results table with Collection column
        self.resultsTable.setColumnCount(8)
        self.resultsTable.setHorizontalHeaderLabels([
            'ID', 'Collection', 'Date', 'Cloud Cover %', 
            'Platform', 'Provider', 'Assets', 'Geometry'
        ])
        self.resultsTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Setup assets table with ID column and Asset Name
        self.assetsTable.setColumnCount(6)
        self.assetsTable.setHorizontalHeaderLabels([
            'Select', 'ID', 'Asset Name', 'Type', 'Size', 'Extension'
        ])
        header = self.assetsTable.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        
        # Set cloud cover slider
        self.cloudCoverSlider.setRange(0, 100)
        self.cloudCoverSlider.setValue(30)
        self.cloudCoverLabel.setText('30%')
        
        # Set limit
        self.limitSpinBox.setValue(50)
        self.limitSpinBox.setRange(1, 500)
        
        # Set default download path
        self.downloadPathEdit.setText(os.path.expanduser('~'))

    def setup_preview_map(self):
        """Setup map preview canvas in Results tab - CORRECTED"""
        # Get the Results tab widget
        results_tab = self.tabWidget.widget(1)
        
        # Get the existing layout
        layout = results_tab.layout()
        if not layout:
            layout = QVBoxLayout(results_tab)
        
        # Add checkbox directly to layout (always visible)
        self.showMapCheck = QCheckBox('Show Item Footprints on Map')
        self.showMapCheck.setChecked(False)
        layout.addWidget(self.showMapCheck)
        
        # Create map canvas container (initially hidden)
        map_canvas_widget = QWidget()
        map_canvas_layout = QVBoxLayout(map_canvas_widget)
        map_canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create map canvas
        self.preview_canvas = QgsMapCanvas()
        self.preview_canvas.setCanvasColor(QColor(255, 255, 255))
        self.preview_canvas.setMinimumHeight(350)
        map_canvas_layout.addWidget(self.preview_canvas)
        
        # Initially hide only the map canvas
        map_canvas_widget.setVisible(False)
        self.map_container = map_canvas_widget
        
        # Add map canvas widget to layout
        layout.addWidget(map_canvas_widget)
        
        # Add basemap layer (Google Satellite)
        self.add_basemap()


    def add_basemap(self):
        """Add Google Satellite basemap to preview canvas"""
        try:
            # Google Satellite XYZ Tile URL
            url = "type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D{x}%26y%3D{y}%26z%3D{z}&zmax=19&zmin=0"
            
            # Create raster layer
            self.basemap_layer = QgsRasterLayer(url, 'Google Satellite', 'wms')
            
            if self.basemap_layer.isValid():
                # Add to preview canvas (don't add to project)
                self.preview_canvas.setLayers([self.basemap_layer])
                self.preview_canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
                self.log_message('Google Satellite basemap loaded successfully', Qgis.Info)
            else:
                # Fallback to OpenStreetMap if Google fails
                url_osm = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
                self.basemap_layer = QgsRasterLayer(url_osm, 'OpenStreetMap', 'wms')
                if self.basemap_layer.isValid():
                    self.preview_canvas.setLayers([self.basemap_layer])
                    self.preview_canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
                    self.log_message('Fallback to OpenStreetMap basemap', Qgis.Info)
                else:
                    self.log_message('Failed to load basemap', Qgis.Warning)
                    self.basemap_layer = None
            
        except Exception as e:
            self.log_message(f'Error loading basemap: {str(e)}', Qgis.Warning)
            self.basemap_layer = None

    def connect_signals(self):
        """Connect UI signals to slots"""
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
        
        # Table selections
        self.resultsTable.itemSelectionChanged.connect(self.on_item_selection_changed)
        
        # Map preview
        self.showMapCheck.stateChanged.connect(self.toggle_map_preview)
        
        # File type filter
        self.fileTypeCombo.currentTextChanged.connect(self.filter_assets_by_type)
        
        # Cloud cover slider
        self.cloudCoverSlider.valueChanged.connect(
            lambda v: self.cloudCoverLabel.setText(f'{v}%')
        )

    def toggle_map_preview(self, state):
        """Toggle map preview visibility"""
        is_visible = state == Qt.Checked
        
        # Show/hide map container
        if hasattr(self, 'map_container'):
            self.map_container.setVisible(is_visible)
        
        # Display footprints if visible
        if is_visible and self.current_items:
            self.display_footprints()
        else:
            # Clear rubber bands
            for rb in self.rubber_bands:
                rb.reset()
            self.rubber_bands = []

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
            
            self.statusLabel.setText(f'Loaded {len(collections)} collections from {connection_name}')
                    
        except Exception as e:
            self.log_message(f'Error populating collections: {str(e)}', Qgis.Warning)
            self.statusLabel.setText('Error loading collections')

    def on_provider_changed(self, provider_text):
        """Handle provider selection change"""
        self.populate_collections()

    def use_canvas_extent(self):
        """Use current map canvas extent as bbox"""
        extent = self.canvas.extent()
        crs = self.canvas.mapSettings().destinationCrs()
        
        # Transform to WGS84 if needed
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

    def clear_bbox(self):
        """Clear bbox inputs"""
        self.bboxWestEdit.clear()
        self.bboxSouthEdit.clear()
        self.bboxEastEdit.clear()
        self.bboxNorthEdit.clear()
        
        if self.rubber_band:
            self.rubber_band.reset()

    def visualize_bbox(self):
        """Visualize bbox on map canvas"""
        try:
            west = float(self.bboxWestEdit.text())
            south = float(self.bboxSouthEdit.text())
            east = float(self.bboxEastEdit.text())
            north = float(self.bboxNorthEdit.text())
            
            if not self.rubber_band:
                from qgis.gui import QgsRubberBand
                from qgis.core import QgsWkbTypes
                self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
                self.rubber_band.setColor(QColor(255, 0, 0, 100))
                self.rubber_band.setWidth(2)
            
            rect = QgsRectangle(west, south, east, north)
            
            crs = self.canvas.mapSettings().destinationCrs()
            if crs.authid() != 'EPSG:4326':
                transform = QgsCoordinateTransform(
                    QgsCoordinateReferenceSystem('EPSG:4326'),
                    crs,
                    QgsProject.instance()
                )
                rect = transform.transformBoundingBox(rect)
            
            self.rubber_band.setToGeometry(rect, crs)
            
        except ValueError:
            pass

    def perform_search(self):
        """Perform search based on user inputs"""
        try:
            if not self.validate_search_params():
                return
            
            connection_name = self.providerCombo.currentText()
            connection = self.connection_manager.get_connection(connection_name)
            
            if not connection:
                self.show_warning('Please select a valid connection')
                return
            
            collections = [item.text() for item in self.collectionList.selectedItems()]
            
            if not collections:
                self.show_warning('Please select at least one collection')
                return
            
            bbox = [
                float(self.bboxWestEdit.text()),
                float(self.bboxSouthEdit.text()),
                float(self.bboxEastEdit.text()),
                float(self.bboxNorthEdit.text())
            ]
            
            start_date = self.startDateEdit.date().toString('yyyy-MM-dd')
            end_date = self.endDateEdit.date().toString('yyyy-MM-dd')
            datetime = f'{start_date}/{end_date}'
            
            cloud_cover = self.cloudCoverSlider.value()
            limit = self.limitSpinBox.value()
            
            self.statusLabel.setText('Searching...')
            self.searchButton.setEnabled(False)
            
            items = self.stac_client.search_items(
                connection=connection,
                collections=collections,
                bbox=bbox,
                datetime=datetime,
                cloud_cover=cloud_cover,
                limit=limit
            )
            
            self.current_items = items
            self.display_results(items)
            
            # Display footprints if map is visible
            if self.showMapCheck.isChecked():
                self.display_footprints()
            
            self.statusLabel.setText(f'Found {len(items)} items')
            self.searchButton.setEnabled(True)
            
            self.tabWidget.setCurrentIndex(1)
            
        except Exception as e:
            self.show_error(f'Search failed: {str(e)}')
            self.statusLabel.setText('Search failed')
            self.searchButton.setEnabled(True)

    def validate_search_params(self):
        """Validate search parameters"""
        try:
            float(self.bboxWestEdit.text())
            float(self.bboxSouthEdit.text())
            float(self.bboxEastEdit.text())
            float(self.bboxNorthEdit.text())
            return True
        except ValueError:
            self.show_warning('Please provide valid bounding box coordinates')
            return False

    def display_results(self, items):
        """Display search results in table"""
        self.resultsTable.setRowCount(0)
        
        for item in items:
            row = self.resultsTable.rowCount()
            self.resultsTable.insertRow(row)
            
            self.resultsTable.setItem(row, 0, QTableWidgetItem(item.id))
            
            collection = item.collection_id if hasattr(item, 'collection_id') else 'N/A'
            self.resultsTable.setItem(row, 1, QTableWidgetItem(str(collection)))
            
            props = item.properties if hasattr(item, 'properties') else {}
            datetime = props.get('datetime', 'N/A')
            if datetime != 'N/A':
                datetime = datetime[:10]
            self.resultsTable.setItem(row, 2, QTableWidgetItem(datetime))
            
            cloud_cover = props.get('eo:cloud_cover', -1)
            if cloud_cover >= 0:
                self.resultsTable.setItem(row, 3, QTableWidgetItem(f'{cloud_cover:.1f}'))
            else:
                self.resultsTable.setItem(row, 3, QTableWidgetItem('N/A'))
            
            platform = props.get('platform', 'N/A')
            self.resultsTable.setItem(row, 4, QTableWidgetItem(platform))
            
            provider = self.providerCombo.currentText()
            self.resultsTable.setItem(row, 5, QTableWidgetItem(provider))
            
            asset_count = len(item.assets) if hasattr(item, 'assets') else 0
            self.resultsTable.setItem(row, 6, QTableWidgetItem(str(asset_count)))
            
            geom_type = item.geometry.get('type', 'N/A') if hasattr(item, 'geometry') and item.geometry else 'N/A'
            self.resultsTable.setItem(row, 7, QTableWidgetItem(geom_type))

    def display_footprints(self):
        """Display item footprints on preview map with basemap and outlines"""
        try:
            # Clear existing rubber bands
            for rb in self.rubber_bands:
                rb.reset()
            self.rubber_bands = []
            
            if not self.current_items:
                return
            
            # Create CRS for footprints (WGS84)
            footprint_crs = QgsCoordinateReferenceSystem('EPSG:4326')
            # Canvas CRS (Web Mercator for basemap)
            canvas_crs = QgsCoordinateReferenceSystem('EPSG:3857')
            
            # Create transform
            transform = QgsCoordinateTransform(
                footprint_crs,
                canvas_crs,
                QgsProject.instance()
            )
            
            # Create bounding box to zoom to
            min_x, min_y, max_x, max_y = 180, 90, -180, -90
            
            # Draw each footprint with outline only
            for idx, item in enumerate(self.current_items):
                if not hasattr(item, 'geometry') or not item.geometry:
                    continue
                
                geom = item.geometry
                
                # Create rubber band for polygons
                from qgis.core import QgsWkbTypes
                rb = QgsRubberBand(self.preview_canvas, QgsWkbTypes.PolygonGeometry)
                
                # Set to outline only (transparent fill)
                rb.setColor(QColor(0, 150, 255, 0))  # Transparent fill
                rb.setStrokeColor(QColor(0, 150, 255, 255))  # Bright blue outline
                rb.setWidth(2)
                rb.setLineStyle(Qt.SolidLine)
                
                # Parse geometry
                if geom['type'] == 'Polygon':
                    coords = geom['coordinates'][0]
                    points = [QgsPointXY(c[0], c[1]) for c in coords]
                    
                    # Create geometry and transform to canvas CRS
                    geom_obj = QgsGeometry.fromPolygonXY([points])
                    geom_obj.transform(transform)
                    
                    rb.setToGeometry(geom_obj, canvas_crs)
                    
                    # Update bounds (in WGS84)
                    for c in coords:
                        min_x = min(min_x, c[0])
                        max_x = max(max_x, c[0])
                        min_y = min(min_y, c[1])
                        max_y = max(max_y, c[1])
                
                self.rubber_bands.append(rb)
            
            # Set extent
            if min_x < max_x and min_y < max_y:
                # Create extent in WGS84
                extent = QgsRectangle(min_x, min_y, max_x, max_y)
                # Add some padding (15%)
                extent.scale(1.15)
                
                # Transform extent to canvas CRS
                extent = transform.transformBoundingBox(extent)
                
                self.preview_canvas.setExtent(extent)
                self.preview_canvas.refresh()
            
        except Exception as e:
            self.log_message(f'Error displaying footprints: {str(e)}', Qgis.Warning)

    def on_item_selection_changed(self):
        """Handle item selection - highlight selected footprints with fill"""
        try:
            if not self.showMapCheck.isChecked():
                return
            
            selected_rows = set(item.row() for item in self.resultsTable.selectedItems())
            
            # Update rubber band styles
            for idx, rb in enumerate(self.rubber_bands):
                if idx in selected_rows:
                    # Highlight selected with red outline and semi-transparent red fill
                    rb.setColor(QColor(255, 50, 50, 128))  # Red with 50% opacity
                    rb.setStrokeColor(QColor(255, 0, 0, 255))  # Solid red outline
                    rb.setWidth(3)
                else:
                    # Normal: blue outline only, no fill
                    rb.setColor(QColor(0, 150, 255, 0))  # Transparent fill
                    rb.setStrokeColor(QColor(0, 150, 255, 255))  # Bright blue outline
                    rb.setWidth(2)
            
            self.preview_canvas.refresh()
            
        except Exception as e:
            self.log_message(f'Error updating selection: {str(e)}', Qgis.Warning)

    def load_selected_item(self):
        """Load selected item's assets to Assets tab"""
        selected_rows = self.resultsTable.selectedItems()
        if not selected_rows:
            self.show_warning('Please select an item from the results')
            return
        
        row = self.resultsTable.currentRow()
        if row < 0 or row >= len(self.current_items):
            return
        
        self.selected_item = self.current_items[row]
        self.display_assets(self.selected_item)
        
        self.tabWidget.setCurrentIndex(2)

    def display_assets(self, item):
        """Display assets for selected item with checkboxes and Item ID"""
        self.assetsTable.setRowCount(0)
        self.current_item_assets = []
        
        self.itemIdLabel.setText(f'Item ID: {item.id}')
        
        if not hasattr(item, 'assets'):
            return
        
        for asset_key, asset in item.assets.items():
            href = asset.href if hasattr(asset, 'href') else ''
            extension = os.path.splitext(href)[1] if href else 'N/A'
            
            self.current_item_assets.append({
                'key': asset_key,
                'asset': asset,
                'extension': extension,
                'item': item
            })
            
            row = self.assetsTable.rowCount()
            self.assetsTable.insertRow(row)
            
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.assetsTable.setCellWidget(row, 0, checkbox_widget)
            
            # ID
            id_item = QTableWidgetItem(item.id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.assetsTable.setItem(row, 1, id_item)
            
            # Asset Name
            self.assetsTable.setItem(row, 2, QTableWidgetItem(asset_key))
            
            # Type
            asset_type = asset.media_type if hasattr(asset, 'media_type') else 'N/A'
            self.assetsTable.setItem(row, 3, QTableWidgetItem(asset_type))
            
            # Size
            size = 'N/A'
            if hasattr(asset, 'extra_fields') and 'file:size' in asset.extra_fields:
                size_bytes = asset.extra_fields['file:size']
                size = self.format_file_size(size_bytes)
            self.assetsTable.setItem(row, 4, QTableWidgetItem(size))
            
            # Extension
            self.assetsTable.setItem(row, 5, QTableWidgetItem(extension))
        
        self.filter_assets_by_type()

    def filter_assets_by_type(self):
        """Filter assets table by selected file type"""
        filter_text = self.fileTypeCombo.currentText()
        
        if filter_text == 'All':
            for row in range(self.assetsTable.rowCount()):
                self.assetsTable.setRowHidden(row, False)
            return
        
        extensions = []
        if '.tif / .tiff' in filter_text:
            extensions = ['.tif', '.tiff']
        elif '.jpg / .jpeg' in filter_text:
            extensions = ['.jpg', '.jpeg']
        else:
            extensions = [filter_text.split()[0]]
        
        for row in range(self.assetsTable.rowCount()):
            ext_item = self.assetsTable.item(row, 5)
            if ext_item:
                ext = ext_item.text().lower()
                should_show = any(ext == e.lower() for e in extensions)
                self.assetsTable.setRowHidden(row, not should_show)

    def get_selected_assets(self):
        """Get list of selected assets with their info"""
        selected = []
        for row in range(self.assetsTable.rowCount()):
            if self.assetsTable.isRowHidden(row):
                continue
                
            checkbox_widget = self.assetsTable.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.current_item_assets):
                        selected.append(self.current_item_assets[row])
        
        return selected

    def load_selected_assets(self):
        """Load selected assets as QGIS layers"""
        if not self.selected_item:
            self.show_warning('Please select an item first')
            return
        
        selected_assets = self.get_selected_assets()
        
        if not selected_assets:
            self.show_warning('Please select at least one asset to load')
            return
        
        try:
            progress = QProgressDialog('Loading assets...', 'Cancel', 0, len(selected_assets), self)
            progress.setWindowModality(Qt.WindowModal)
            
            loaded = 0
            for i, asset_info in enumerate(selected_assets):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f'Loading {asset_info["key"]}...')
                
                try:
                    self.layer_loader.load_cog_layer(
                        asset_info['item'],
                        asset_info['key']
                    )
                    loaded += 1
                except Exception as e:
                    self.log_message(f'Failed to load {asset_info["key"]}: {str(e)}', Qgis.Warning)
            
            progress.setValue(len(selected_assets))
            self.show_info(f'Successfully loaded {loaded}/{len(selected_assets)} assets')
            
        except Exception as e:
            self.show_error(f'Failed to load assets: {str(e)}')

    def browse_download_path(self):
        """Browse for download directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            'Select Download Directory',
            self.downloadPathEdit.text()
        )
        
        if directory:
            self.downloadPathEdit.setText(directory)

    def download_assets(self):
        """Download selected assets without folder structure"""
        self._download_assets(structured=False)

    def download_assets_structured(self):
        """Download selected assets with ID folder structure"""
        self._download_assets(structured=True)

    def _download_assets(self, structured=False):
        """Download assets with structure: <ID>/<AssetName>.<ext>"""
        if not self.selected_item:
            self.show_warning('Please select an item first')
            return
        
        selected_assets = self.get_selected_assets()
        
        if not selected_assets:
            self.show_warning('Please select at least one asset to download')
            return
        
        download_path = self.downloadPathEdit.text()
        
        if not download_path or not os.path.exists(download_path):
            self.show_warning('Please select a valid download directory')
            return
        
        try:
            progress = QProgressDialog('Downloading assets...', 'Cancel', 0, len(selected_assets), self)
            progress.setWindowModality(Qt.WindowModal)
            
            downloaded = 0
            
            if structured:
                item_folder = os.path.join(download_path, self.selected_item.id)
                os.makedirs(item_folder, exist_ok=True)
                base_path = item_folder
            else:
                base_path = download_path
            
            for i, asset_info in enumerate(selected_assets):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f'Downloading {asset_info["key"]}...')
                
                try:
                    asset = asset_info['asset']
                    extension = asset_info['extension']
                    asset_name = asset_info['key']
                    
                    if extension and extension != 'N/A':
                        filename = f'{asset_name}{extension}'
                    else:
                        href = asset.href if hasattr(asset, 'href') else ''
                        ext_from_url = os.path.splitext(href)[1]
                        filename = f'{asset_name}{ext_from_url}' if ext_from_url else asset_name
                    
                    filepath = os.path.join(base_path, filename)
                    
                    self.stac_client.download_asset(asset, filepath)
                    downloaded += 1
                    
                except Exception as e:
                    self.log_message(f'Failed to download {asset_info["key"]}: {str(e)}', Qgis.Warning)
            
            progress.setValue(len(selected_assets))
            
            self.show_info(f'Successfully downloaded {downloaded}/{len(selected_assets)} assets\n\nLocation: {base_path}')
            
        except Exception as e:
            self.show_error(f'Download failed: {str(e)}')

    def format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f'{size_bytes:.2f} {unit}'
            size_bytes /= 1024.0
        return f'{size_bytes:.2f} TB'

    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, 'Error', message)
        self.log_message(message, Qgis.Critical)

    def show_warning(self, message):
        """Show warning message"""
        QMessageBox.warning(self, 'Warning', message)

    def show_info(self, message):
        """Show info message"""
        QMessageBox.information(self, 'Information', message)

    def log_message(self, message, level=Qgis.Info):
        """Log message to QGIS"""
        QgsMessageLog.logMessage(message, 'Open Geodata Browser', level)
    
    def closeEvent(self, event):
        """Clean up when dialog closes"""
        # Clear rubber bands
        for rb in self.rubber_bands:
            rb.reset()
        self.rubber_bands = []
        
        if self.rubber_band:
            self.rubber_band.reset()
        
        event.accept()
