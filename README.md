# SPC Outlook Tool

Downloads historical SPC outlooks from Iowa Environmental Mesonet (IEM) and generates shapefiles, GeoJSON, PNG images, and interactive HTML maps.

## Features

- **Multi-day support**: Day 1, 2, and 3 outlooks
- **Outlook types**: Convective and Fire Weather
- **Flexible output**: Shapefiles, GeoJSON, PNG maps, interactive HTML
- **Selective generation**: Choose specific hazards, cycles, and formats
- **Automatic fallback**: Handles different geometry types (layered/non-layered)

## What it does

- Fetches SPC outlooks for any date (Day 1/2/3)
- Supports both convective and fire weather outlooks
- Saves shapefiles and GeoJSON for selected hazard types
- Generates PNG maps with proper SPC colors and US state boundaries
- Creates interactive HTML maps with toggleable layers
- Flexible filtering by hazard type, cycle, and output format

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

**Get categorical outlook (includes all risk levels):**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard categorical
```

**Get ONLY thunderstorm areas (TSTM):**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard tstm
```

**Specific cycle (20Z):**
```bash
python spc_outlook_tool.py 2025-03-14 --cycle 20z
```

**Quick download (no processing):**
```bash
python spc_outlook_tool.py 2025-03-14 --quick
```

### Multi-Day Examples

**Day 2 outlook:**
```bash
python spc_outlook_tool.py 2025-03-14 --day 2
```

**Day 3 categorical only:**
```bash
python spc_outlook_tool.py 2025-03-14 --day 3 --hazard categorical
```

### Fire Weather Examples

**Fire weather outlook (Day 1):**
```bash
python spc_outlook_tool.py 2025-07-20 --type fire
```

**Fire weather Day 2:**
```bash
python spc_outlook_tool.py 2025-07-20 --type fire --day 2
```

**Just fire shapefiles:**
```bash
python spc_outlook_tool.py 2025-07-20 --type fire --hazard fire --format shp
```

### Options

- `--day, -d`: Outlook day
  - Options: `1`, `2`, `3`
  - Default: `1`
  
- `--type, -t`: Outlook type
  - Options: `convective`, `fire`
  - Default: `convective`

- `--hazard, -H`: Specific hazard types (comma-separated)
  - For convective: `categorical`, `tornado`, `wind`, `hail`, `tstm`
  - For fire: `fire`, `dryt`
  - Default: all hazards
  - Note: `tstm` extracts only the general thunderstorm areas (TSTM threshold)
  
- `--format, -f`: Output formats (comma-separated)
  - Options: `shp`, `geojson`, `png`, `html`
  - Default: all formats
  
- `--cycle, -c`: Specific cycle or "latest"
  - Options: `01z`, `06z`, `13z`, `1630z`, `20z`, `latest`
  - Default: all cycles
  
- `--output, -o`: Output directory
  - Default: `./output`
  
- `--quick`: Download only, no processing

### Examples

**Day 1 outlook (default):**
```bash
python spc_outlook_tool.py 2025-03-14
```

**Day 2 outlook:**
```bash
python spc_outlook_tool.py 2025-03-14 --day 2
```

**Day 3 categorical outlook only:**
```bash
python spc_outlook_tool.py 2025-03-14 --day 3 --hazard categorical
```

**Fire weather outlook:**
```bash
python spc_outlook_tool.py 2025-03-14 --type fire
```

**Just tornado shapefiles:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard tornado --format shp
```

**PNG maps of categorical and tornado for latest update:**
```bash
python spc_outlook_tool.py 2025-03-14 --hazard categorical,tornado --format png --cycle latest
```

**Interactive HTML map with all hazards:**
```bash
python spc_outlook_tool.py 2025-03-14 --format html
```

## Output Structure

```
output/
└── 2025-03-14_day1_convective/
    ├── raw_data_day1_2025-03-14.zip     # Original IEM download
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
    ├── cycle_1630z/
    └── cycle_20z/
```

## Important Notes

- **Data source**: Iowa Environmental Mesonet (unofficial SPC archive)
- **Archive coverage**: Back to 1987 for convective outlooks
- **Update cycles vary by day**:
  - Day 1: 01Z, 06Z, 13Z, 1630Z, 20Z (5 updates)
  - Day 2: 07Z, 17Z (2 updates)
  - Day 3: 08Z, 20Z (2 updates)
- **Fire weather cycles**: 07Z, 17Z
- **Times**: All times are UTC
- **Fire weather categories**: ELEV (Elevated), CRIT (Critical), EXTM (Extreme)

## Hazard Types

### Convective Outlooks

**Categorical**: General risk levels
- TSTM (General Thunder) - The basic thunderstorm outlook
- MRGL (Marginal Risk)  
- SLGT (Slight Risk)
- ENH (Enhanced Risk)
- MDT (Moderate Risk)
- HIGH (High Risk)

**Note**: The thunderstorm outlook (TSTM) is included in the categorical outlook. When you request categorical data, you get all risk levels including the general thunderstorm areas.

**Probabilistic**: Specific hazard probabilities
- Tornado: 2%, 5%, 10%, 15%, 30%, 45%, 60%, SIGN (Significant)
- Wind: 5%, 15%, 30%, 45%, 60%, SIGN (Significant)
- Hail: 5%, 15%, 30%, 45%, 60%, SIGN (Significant)

### Fire Weather Outlooks

- ELEV (Elevated)
- CRIT (Critical)
- EXTM (Extreme)
- ISODRYT (Isolated Dry Thunderstorm)
- DRYT (Dry Thunderstorm)
- SCTDRYT (Scattered Dry Thunderstorm)

## Troubleshooting

**No data found**: Try a different date. Not all dates have outlooks.

**422 Error**: The tool automatically tries different data formats. If it still fails, that date might not be available.

**Missing dependencies**: Make sure geopandas is installed with all its dependencies (GDAL, etc). Conda handles this better than pip.

**Fire weather not showing**: Fire weather outlooks may not be available for all dates. They're typically issued during fire season.

**Empty PNG/plots**: Some hazard types may not have data for the selected date. This is normal.

## Data Availability

- **Convective outlooks**: Available most days during severe weather season (March-September)
- **Fire weather outlooks**: Primarily during fire season (varies by region)
- **Historical data**: Goes back to 1987 for convective outlooks
- **Real-time data**: Usually available within minutes of SPC issuance