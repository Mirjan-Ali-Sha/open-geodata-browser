# Open Geodata Browser - QGIS Plugin

Browse and access satellite imagery from multiple STAC providers directly in QGIS.

## Features

- **Multi-Provider Support**: Access Microsoft Planetary Computer and AWS EarthSearch
- **Advanced Search**: Filter by spatial extent, date range, cloud cover, and more
- **Direct COG Loading**: Load Cloud-Optimized GeoTIFFs directly into QGIS
- **Batch Operations**: Download multiple assets at once
- **Provider Comparison**: Compare data availability across providers
- **Automatic URL Management**: Automatic signing for Planetary Computer

## Installation

### Prerequisites

Install Open-Geodata-API in your QGIS Python environment:

From QGIS Python Console
```
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "open-geodata-api"])
```

### Plugin Installation

1. Download the plugin zip file
2. In QGIS, go to `Plugins > Manage and Install Plugins`
3. Click "Install from ZIP"
4. Select the downloaded zip file
5. Enable the plugin

## Usage

1. Click the Open Geodata Browser icon in the toolbar
2. Select a data provider (Planetary Computer or EarthSearch)
3. Choose one or more collections
4. Set filters (date range, cloud cover, bounding box)
5. Click "Search"
6. Select an item from results
7. Load assets directly to QGIS or download them

## Requirements

- QGIS >= 3.0
- Python packages:
  - open-geodata-api >= 1.0.0

## License

GPL v3

## Author

Mirjan Ali Sha (mastools.help@gmail.com)



