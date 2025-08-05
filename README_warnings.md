# IEM Warnings Tool

Fetches current NWS watches, warnings, and advisories from the Iowa Environmental Mesonet (IEM) and converts them to GeoJSON or Shapefile format.

## Features

- **Real-time Data**: Fetches current active warnings from IEM's Storm Based Warning API
- **Multiple Formats**: Output as GeoJSON or Shapefile
- **Flexible Filtering**: Filter by WFO, hazard type, or significance level
- **Human-Readable**: Option to list warnings in console with details
- **Polygon Data**: Full storm-based warning polygons, not just counties

## Setup

Uses the same environment as the SPC Outlook Tool:

```bash
# If you haven't already set up the environment
conda activate spc-tool
# or
source venv/bin/activate
```

## Usage

### Basic Examples

**Get all current warnings as GeoJSON:**
```bash
python iem_warnings_tool.py
```

**List all warnings to console:**
```bash
python iem_warnings_tool.py --list
```

**Get warnings for a specific Weather Forecast Office:**
```bash
python iem_warnings_tool.py --wfo DMX --list
```

**Get only tornado warnings:**
```bash
python iem_warnings_tool.py --phenomena TO --format both
```

**Get all severe thunderstorm warnings as shapefile:**
```bash
python iem_warnings_tool.py --phenomena SV --format shp
```

**Get only warnings (no watches or advisories):**
```bash
python iem_warnings_tool.py --significance W
```

### Options

- `--output, -o`: Output directory (default: `./warnings_output`)
- `--format, -f`: Output format
  - `geojson` (default)
  - `shp` (shapefile)
  - `both`
- `--wfo, -w`: Filter by Weather Forecast Office code (e.g., DMX, OUN)
- `--phenomena, -p`: Filter by hazard type
- `--significance, -g`: Filter by significance level
- `--list, -l`: Display warnings in console

### Common Phenomena Codes

**Severe Weather:**
- `TO` - Tornado
- `SV` - Severe Thunderstorm
- `FF` - Flash Flood
- `FL` - Flood
- `SQ` - Snow Squall

**Winter Weather:**
- `BZ` - Blizzard
- `WS` - Winter Storm
- `WW` - Winter Weather

**Other Hazards:**
- `HW` - High Wind
- `EW` - Extreme Wind
- `FW` - Fire Weather
- `HU` - Hurricane
- `TR` - Tropical Storm
- `EH` - Excessive Heat
- `DS` - Dust Storm

### Significance Codes

- `W` - Warning (highest priority)
- `A` - Watch
- `Y` - Advisory
- `S` - Statement

## Output

The tool creates timestamped files in the output directory:

```
warnings_output/
├── warnings_20250804_033154Z.geojson
├── warnings_20250804_033154Z_SV.geojson
└── warnings_20250804_033154Z_TO_W.shp
```

## GeoJSON Properties

Each warning polygon includes these properties:
- `phenomena`: Hazard type code
- `significance`: Warning level code
- `ps`: Human-readable product name
- `wfo`: Issuing office
- `eventid`: Event number
- `issue`: Issue time (UTC)
- `expire`: Expiration time (UTC)
- `windtag`: Max wind speed (mph) for severe thunderstorms
- `hailtag`: Max hail size (inches) for severe thunderstorms
- `tornadotag`: Tornado tag if applicable
- `is_emergency`: Emergency warning flag
- `is_pds`: Particularly Dangerous Situation flag

## Examples

**Monitor tornado warnings in real-time:**
```bash
# Run every few minutes
watch -n 120 python iem_warnings_tool.py --phenomena TO --list
```

**Get all warnings for your state's WFO:**
```bash
# Find your WFO at https://www.weather.gov/
python iem_warnings_tool.py --wfo MKX --format both --list
```

**Emergency warnings only:**
```bash
# Would need to add custom filtering for emergency warnings
python iem_warnings_tool.py --list | grep EMERGENCY
```

## Data Source

This tool uses the Iowa Environmental Mesonet's Storm Based Warning API:
- Endpoint: `https://mesonet.agron.iastate.edu/geojson/sbw.py`
- Updates: Real-time (typically within seconds of NWS issuance)
- Coverage: All US NWS offices
- History: Current active warnings only (for historical data, use the watchwarn.phtml interface)

## Limitations

- State filtering is not implemented (would require state boundary data)
- Only shows currently active warnings (no historical data)
- Some warnings may not have full polygon data
- Shapefile column names are truncated to 10 characters (ESRI limitation)

## Tips

1. **Check specific hazards during events:**
   ```bash
   python iem_warnings_tool.py --phenomena SV,TO --list
   ```

2. **Save warnings during major events:**
   ```bash
   python iem_warnings_tool.py --format both --output ./storm_archive/$(date +%Y%m%d)
   ```

3. **Convert to other formats:**
   ```bash
   # Use ogr2ogr to convert to KML, etc.
   ogr2ogr -f KML warnings.kml warnings_output/warnings_*.shp
   ```