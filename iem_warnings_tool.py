#!/usr/bin/env python3
"""
IEM Warnings Tool - Fetches current NWS watches/warnings from Iowa Environmental Mesonet
Outputs as GeoJSON, Shapefile, or other formats
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests
import geopandas as gpd
from shapely.geometry import shape

# IEM API endpoints
SBW_ENDPOINT = "https://mesonet.agron.iastate.edu/geojson/sbw.py"
VTEC_EVENT_ENDPOINT = "https://mesonet.agron.iastate.edu/geojson/vtec_event.py"

# VTEC phenomena codes
PHENOMENA = {
    'TO': 'Tornado',
    'SV': 'Severe Thunderstorm',
    'FF': 'Flash Flood',
    'FL': 'Flood',
    'MA': 'Marine',
    'FA': 'Areal Flood Advisory',
    'SQ': 'Snow Squall',
    'BZ': 'Blizzard',
    'WS': 'Winter Storm',
    'WW': 'Winter Weather',
    'HW': 'High Wind',
    'EW': 'Extreme Wind',
    'FW': 'Fire Weather',
    'HU': 'Hurricane',
    'TR': 'Tropical Storm',
    'TY': 'Typhoon',
    'EH': 'Excessive Heat',
    'HT': 'Heat',
    'FZ': 'Freeze',
    'FR': 'Frost',
    'CF': 'Coastal Flood',
    'LS': 'Lakeshore Flood',
    'SU': 'High Surf',
    'RP': 'Rip Current',
    'DS': 'Dust Storm'
}

# VTEC significance codes
SIGNIFICANCE = {
    'W': 'Warning',
    'A': 'Watch',
    'Y': 'Advisory',
    'S': 'Statement',
    'F': 'Forecast',
    'O': 'Outlook',
    'N': 'Synopsis'
}


def fetch_current_warnings(wfo=None, state=None, phenomena=None, significance=None):
    """Fetch current warnings from IEM Storm Based Warnings endpoint"""
    print("\nFetching current warnings from IEM...")
    
    # Build query parameters
    params = {}
    if wfo:
        params['wfo'] = wfo.upper()
    # Note: The SBW endpoint may not support all filters, we'll parse client-side if needed
    
    try:
        response = requests.get(SBW_ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"  Received {data.get('count', 0)} warnings")
        
        # Filter client-side if needed
        features = data.get('features', [])
        
        if state:
            # Would need state boundaries to filter properly
            print(f"  Note: State filtering not implemented yet")
        
        if phenomena:
            phenomena_upper = phenomena.upper()
            features = [f for f in features if f['properties'].get('phenomena') == phenomena_upper]
            print(f"  Filtered to {len(features)} {PHENOMENA.get(phenomena_upper, phenomena_upper)} warnings")
        
        if significance:
            sig_upper = significance.upper()
            features = [f for f in features if f['properties'].get('significance') == sig_upper]
            print(f"  Filtered to {len(features)} {SIGNIFICANCE.get(sig_upper, sig_upper)}s")
        
        data['features'] = features
        data['count'] = len(features)
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching warnings: {e}")
        return None


def save_geojson(data, output_path):
    """Save data as GeoJSON"""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  Saved GeoJSON: {output_path}")


def save_shapefile(data, output_path):
    """Convert GeoJSON to Shapefile"""
    if not data or not data.get('features'):
        print("  No features to save as shapefile")
        return
    
    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    
    # Ensure valid geometries
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom if geom.is_valid else geom.buffer(0))
    
    # Save shapefile
    gdf.to_file(output_path, driver='ESRI Shapefile')
    print(f"  Saved Shapefile: {output_path}")


def format_warning_info(feature):
    """Format warning information for display"""
    props = feature['properties']
    
    phenomena_code = props.get('phenomena', 'UNK')
    phenomena_name = PHENOMENA.get(phenomena_code, phenomena_code)
    
    sig_code = props.get('significance', 'UNK')
    sig_name = SIGNIFICANCE.get(sig_code, sig_code)
    
    wfo = props.get('wfo', 'UNK')
    event_id = props.get('eventid', 'UNK')
    
    issue_time = props.get('issue', 'Unknown')
    expire_time = props.get('expire', 'Unknown')
    
    # Special tags
    tags = []
    if props.get('is_emergency'):
        tags.append('EMERGENCY')
    if props.get('is_pds'):
        tags.append('PDS')
    if props.get('tornadotag'):
        tags.append(f"Tornado: {props['tornadotag']}")
    if props.get('windtag'):
        tags.append(f"Wind: {props['windtag']} mph")
    if props.get('hailtag'):
        tags.append(f"Hail: {props['hailtag']}\"")
    
    info = f"{phenomena_name} {sig_name} ({phenomena_code}.{sig_code}) - {wfo} #{event_id}"
    if tags:
        info += f" [{', '.join(tags)}]"
    info += f"\n  Issued: {issue_time}"
    info += f"\n  Expires: {expire_time}"
    
    return info


def main():
    parser = argparse.ArgumentParser(
        description='Fetch current NWS watches/warnings from IEM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Get all current warnings
  %(prog)s
  
  # Get warnings for specific WFO
  %(prog)s --wfo DMX
  
  # Get only tornado warnings
  %(prog)s --phenomena TO
  
  # Get all severe thunderstorm warnings as shapefile
  %(prog)s --phenomena SV --format shp
  
  # Get all warnings (W) only, no watches
  %(prog)s --significance W
        '''
    )
    
    parser.add_argument('--output', '-o', default='./warnings_output',
                       help='Output directory')
    parser.add_argument('--format', '-f', default='geojson',
                       choices=['geojson', 'shp', 'both'],
                       help='Output format (default: geojson)')
    parser.add_argument('--wfo', '-w',
                       help='Filter by Weather Forecast Office (e.g., DMX)')
    parser.add_argument('--state', '-s',
                       help='Filter by state (not implemented yet)')
    parser.add_argument('--phenomena', '-p',
                       help='Filter by phenomena (TO=Tornado, SV=Severe Tstorm, FF=Flash Flood)')
    parser.add_argument('--significance', '-g',
                       help='Filter by significance (W=Warning, A=Watch, Y=Advisory)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List warnings to console')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Fetch current warnings
    data = fetch_current_warnings(
        wfo=args.wfo,
        state=args.state,
        phenomena=args.phenomena,
        significance=args.significance
    )
    
    if not data:
        print("Failed to fetch warnings")
        sys.exit(1)
    
    # Generate timestamp for filenames
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
    
    # Build filename base
    filename_parts = ['warnings', timestamp]
    if args.wfo:
        filename_parts.append(f'wfo_{args.wfo}')
    if args.phenomena:
        filename_parts.append(f'{args.phenomena}')
    if args.significance:
        filename_parts.append(f'{args.significance}')
    
    filename_base = '_'.join(filename_parts)
    
    # Save outputs
    if args.format in ['geojson', 'both']:
        geojson_path = output_dir / f'{filename_base}.geojson'
        save_geojson(data, geojson_path)
    
    if args.format in ['shp', 'both']:
        shp_path = output_dir / f'{filename_base}.shp'
        save_shapefile(data, shp_path)
    
    # List warnings if requested
    if args.list and data.get('features'):
        print(f"\nCurrent Warnings ({len(data['features'])} total):")
        print("=" * 70)
        for feature in data['features']:
            print(format_warning_info(feature))
            print("-" * 70)
    
    print(f"\n✓ Complete! Found {data.get('count', 0)} warnings")
    print(f"  Valid at: {data.get('valid_at', 'Unknown')}")
    print(f"  Output directory: {output_dir}")


if __name__ == '__main__':
    main()