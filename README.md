# SPC Outlook Tool

A command-line tool to download, process, and visualize historical SPC (Storm Prediction Center) outlooks from the Iowa Environmental Mesonet (IEM).

**Also includes**: `iem_warnings_tool.py` for fetching current NWS watches/warnings as GeoJSON. See [README_warnings.md](README_warnings.md) for details.

## Features

- **Comprehensive Coverage**: Fetches Day 1, 2, and 3 outlooks for both Convective and Fire Weather.
- **Multiple Formats**: Generates Shapefiles, GeoJSON, high-quality PNG maps, and interactive HTML maps.
- **Highly Customizable**: Filter by date, outlook day, hazard type, and specific issuance cycle.
- **User-Friendly**: Simplified command-line interface with clear, helpful instructions and verbose logging for debugging.
- **Robust**: Handles common data inconsistencies and provides clear error messages.

## Setup

For the most reliable setup, it is highly recommended to use Conda, as it correctly handles complex geospatial dependencies.

### Option 1: Conda (Recommended)
```bash
# Create a new conda environment
conda create -n spc-tool python=3.10

# Activate the environment
conda activate spc-tool

# Install required packages from the conda-forge channel
conda install -c conda-forge geopandas matplotlib requests folium pandas shapely
```

### Option 2: pip
If you prefer pip, you can install the packages from the `requirements.txt` file. Note that installing `geopandas` with pip can be challenging on some systems.
```bash
# It is recommended to use a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

The script is run from the command line, providing the date as the primary argument.

### Basic Examples

**Get today's latest Day 1 outlook and generate all outputs:**
```bash
# The date must be in YYYY-MM-DD format
python spc_outlook_tool.py $(date -u +%Y-%m-%d)
```

**Get the outlook for a specific past date:**
```bash
python spc_outlook_tool.py 2025-03-14
```

### Advanced Examples

**Get a specific cycle (e.g., 1630z) and save as PNG and GeoJSON:**
```bash
python spc_outlook_tool.py 2025-03-14 --cycle 1630z --format png,geojson
```

**Get the Day 2 Fire Weather outlook:**
```bash
python spc_outlook_tool.py 2025-07-21 --day 2 --type fire
```

**Get only the tornado outlooks in shapefile format:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard tornado --format shp
```

**See more detailed output for debugging:**
```bash
python spc_outlook_tool.py 2025-03-14 --verbose
```

**Download the raw data only without processing:**
```bash
python spc_outlook_tool.py 2025-03-14 --quick
```

## Command-Line Options

| Argument | Alias | Description | Choices | Default |
|---|---|---|---|---|
| `date` | | The outlook date in YYYY-MM-DD format. | | Required |
| `--output` | `-o` | Root directory to save output files. | | `./output` |
| `--day` | `-d` | The outlook day. | `1`, `2`, `3` | `1` |
| `--type` | `-t` | The type of outlook. | `convective`, `fire` | `convective` |
| `--hazard` | `-H` | Comma-separated list of hazards. | `categorical`, `tornado`, `wind`, `hail`, `tstm`, `fire`, `dryt` | All for type |
| `--format` | `-f` | Comma-separated list of output formats. | `shp`, `geojson`, `png`, `html` | All formats |
| `--cycle` | `-c` | Specific cycle to process. | `01z`, `13z`, `1630z`, `latest`, `all` | `all` |
| `--quick`| | If set, only downloads the raw data. | | `False` |
| `--verbose`| `-v` | Enable detailed debug logging. | | `False` |


## Output Structure

The tool organizes output into a clean, predictable directory structure.

```
output/
└── 2025-03-14_day1_convective/
    ├── raw_data_day1_2025-03-14.zip
    ├── interactive_map_2025-03-14.html
    └── cycle_1630z/
        ├── categorical_2025-03-14_1630z.shp
        ├── categorical_2025-03-14_1630z.geojson
        ├── categorical_2025-03-14_1630z.png
        └── ... (other hazards)
```

## Important Notes

- **Data Source**: All data is sourced from the unofficial, but highly reliable, SPC outlook archive maintained by the Iowa Environmental Mesonet (IEM).
- **Times**: All cycle times are in UTC. The `1630z` cycle is correctly handled.
- **Dependencies**: Ensure all required Python packages are installed. Using Conda is the most reliable method.
