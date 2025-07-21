# SPC Outlook Tool

Downloads historical SPC Day 1 outlooks from Iowa Environmental Mesonet and generates shapefiles + PNG images.

## What it does

- Fetches all Day 1 outlook updates for a specific date (usually 5 per day)
- Saves shapefiles for tornado, wind, hail, and categorical outlooks
- Generates PNG maps with proper SPC colors and US state boundaries
- Creates an interactive HTML map with all cycles and hazards
- Outputs GeoJSON files too

## Setup

### Option 1: Conda (recommended)
```bash
conda create -n spc python=3.10
conda activate spc
conda install -c conda-forge geopandas matplotlib requests folium
```

### Option 2: pip
```bash
pip install geopandas matplotlib requests pandas shapely folium
```

## Usage

### Basic Usage

Generate everything for a date (all hazards, all formats, all cycles):
```bash
python spc_outlook_tool.py 2025-03-14
```

### Selective Options

**Just tornado shapefiles:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard tornado --format shp
```

**Categorical outlook PNG for latest cycle only:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard categorical --format png --cycle latest
```

**Multiple hazards and formats:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard tornado,wind --format shp,png
```

**Specific cycle (20Z):**
```bash
python spc_outlook_tool.py 2025-03-14 --cycle 20z
```

**Quick download (no processing):**
```bash
python spc_outlook_tool.py 2025-03-14 --quick
```

### Options

- `--hazard, -H`: Specific hazard types (comma-separated)
  - Options: `categorical`, `tornado`, `wind`, `hail`
  - Default: all hazards
  
- `--format, -f`: Output formats (comma-separated)
  - Options: `shp`, `geojson`, `png`, `html`
  - Default: all formats
  
- `--cycle, -c`: Specific cycle or "latest"
  - Options: `01z`, `06z`, `13z`, `16z`, `20z`, `latest`
  - Default: all cycles
  
- `--output, -o`: Output directory
  - Default: `./output`
  
- `--quick`: Download only, no processing

### Examples

**Friend wants just tornado shapefiles for March 14:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard tornado --format shp
```

**Need PNG maps of categorical and tornado for latest update:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard categorical,tornado --format png --cycle latest
```

**Just want the interactive HTML map with all hazards:**
```bash
python spc_outlook_tool.py 2025-03-14 --format html
```

## Output Structure

```
output/
└── 2025-03-14/
    ├── raw_data_2025-03-14.zip          # Original IEM download
    ├── interactive_map_2025-03-14.html  # Interactive web map
    ├── cycle_01z/
    │   ├── categorical_2025-03-14_01z.shp  # Shapefiles
    │   ├── categorical_2025-03-14_01z.geojson
    │   ├── categorical_2025-03-14_01z.png  # PNG images
    │   ├── tornado_2025-03-14_01z.shp
    │   ├── tornado_2025-03-14_01z.png
    │   ├── wind_2025-03-14_01z.shp
    │   ├── wind_2025-03-14_01z.png
    │   ├── hail_2025-03-14_01z.shp
    │   └── hail_2025-03-14_01z.png
    ├── cycle_06z/
    │   └── ... (same structure)
    ├── cycle_13z/
    ├── cycle_16z/
    └── cycle_20z/
```

## Notes

- Data comes from IEM's unofficial archive (not official SPC)
- Archive goes back to 1987 for convective outlooks
- Each day typically has 5 outlook updates (01Z, 06Z, 13Z, 16Z, 20Z)
- All times are UTC

## Hazard Types

**Categorical**: General risk levels
- TSTM (Thunder)
- MRGL (Marginal)  
- SLGT (Slight)
- ENH (Enhanced)
- MDT (Moderate)
- HIGH (High)

**Probabilistic**: Specific hazard probabilities
- Tornado: 2%, 5%, 10%, 15%, 30%, 45%, 60%
- Wind: 5%, 15%, 30%, 45%, 60%
- Hail: 5%, 15%, 30%, 45%, 60%

## Troubleshooting

**No data found**: Try a different date. Not all dates have outlooks.

**422 Error**: The tool automatically tries different data formats. If it still fails, that date might not be available.

**Missing dependencies**: Make sure geopandas is installed with all its dependencies (GDAL, etc). Conda handles this better than pip.