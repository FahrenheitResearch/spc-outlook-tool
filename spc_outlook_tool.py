#!/usr/bin/env python3
"""
SPC Outlook Tool - Downloads and processes SPC outlooks from IEM
Supports Day 1/2/3 convective, thunderstorm, and fire weather outlooks
Generates shapefiles, GeoJSON, PNG images, and interactive HTML maps
"""

import os
import sys
import io
import json
import zipfile
import tempfile
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Core deps
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Plotting
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# For interactive maps
try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False


# IEM API endpoint
BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/spc_outlooks.py"

# Outlook colors
COLORS = {
    'categorical': {
        'TSTM': '#40E0D0',
        'MRGL': '#66FF66', 
        'SLGT': '#FFD700',
        'ENH': '#FF8C00',
        'MDT': '#FF0000',
        'HIGH': '#FF00FF'
    },
    'tornado': {
        '0.02': '#006600',
        '0.05': '#228B22',
        '0.10': '#FFFF00',
        '0.15': '#FFA500',
        '0.30': '#FF0000',
        '0.45': '#FF00FF',
        '0.60': '#912CEE',
        'SIGN': '#FF00FF'  # Significant tornado
    },
    'wind': {
        '0.05': '#8B4513',
        '0.15': '#FFD700',
        '0.30': '#FF0000',
        '0.45': '#FF00FF',
        '0.60': '#912CEE',
        'SIGN': '#FF00FF'  # Significant wind
    },
    'hail': {
        '0.05': '#8B4513',
        '0.15': '#FFD700',
        '0.30': '#FF0000', 
        '0.45': '#FF00FF',
        '0.60': '#912CEE',
        'SIGN': '#FF00FF'  # Significant hail
    },
    'fire': {
        'ELEV': '#FFA500',      # Elevated
        'CRIT': '#FF0000',      # Critical
        'EXTM': '#FF00FF',      # Extreme
        'ISODRYT': '#8B4513',   # Isolated Dry Thunderstorm
        'DRYT': '#D2691E',      # Dry Thunderstorm
        'SCTDRYT': '#DEB887'    # Scattered Dry Thunderstorm
    }
}


def fetch_outlook_data(date_str, output_dir, day=1, outlook_type='C'):
    """Download outlook data from IEM
    
    Args:
        date_str: Date in YYYY-MM-DD format
        output_dir: Output directory
        day: Outlook day (1, 2, or 3)
        outlook_type: 'C' (Convective), 'F' (Fire Weather)
    """
    type_names = {
        'C': 'Convective',
        'F': 'Fire Weather'
    }
    print(f"\nFetching Day {day} {type_names.get(outlook_type, outlook_type)} outlook for {date_str}...")
    
    # Parse date and create UTC range
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    start_utc = dt.strftime('%Y-%m-%dT00:00Z')
    end_utc = (dt + timedelta(days=1)).strftime('%Y-%m-%dT00:00Z')
    
    # Build request
    params = {
        'd': str(day),
        'type': outlook_type,
        'sts': start_utc,
        'ets': end_utc
    }
    
    # Try both geometries (IEM quirk)
    for geom in [None, 'lyr', 'nolyr']:
        if geom:
            params['geom'] = geom
            
        print(f"  Trying geometry: {geom or 'default'}...")
        
        try:
            r = requests.get(BASE_URL, params=params, timeout=60)
            if r.status_code == 200:
                # Save raw zip
                zip_path = os.path.join(output_dir, f'raw_data_day{day}_{date_str}.zip')
                with open(zip_path, 'wb') as f:
                    f.write(r.content)
                print(f"  Success! Downloaded {len(r.content)/1024:.1f} KB")
                return zip_path
            elif r.status_code == 422:
                continue
        except Exception as e:
            print(f"  Failed: {e}")
            
    raise RuntimeError("Could not fetch data - try a different date")


def process_shapefiles(zip_path, output_dir, date_str):
    """Extract and process shapefiles by hazard type"""
    print("\nProcessing shapefiles...")
    
    # Extract zip
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)
            
        # Load all shapefiles
        all_data = []
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f.endswith('.shp'):
                    shp_path = os.path.join(root, f)
                    gdf = gpd.read_file(shp_path)
                    all_data.append(gdf)
                    
        if not all_data:
            raise RuntimeError("No shapefiles found in archive")
            
        # Combine all
        combined = pd.concat(all_data, ignore_index=True)
        print(f"  Loaded {len(combined)} polygons")
        
        # Get unique cycles
        cycles = sorted(combined['CYCLE'].unique()) if 'CYCLE' in combined.columns else [0]
        print(f"  Found cycles: {cycles}")
        
        # Process each cycle
        for cycle in cycles:
            print(f"\n  Processing cycle {cycle}Z...")
            cycle_data = combined[combined['CYCLE'] == cycle] if 'CYCLE' in combined.columns else combined
            
            # Save by hazard type
            hazards = {
                'categorical': cycle_data[cycle_data['CATEGORY'] == 'CATEGORICAL'],
                'tornado': cycle_data[cycle_data['CATEGORY'] == 'TORNADO'],
                'wind': cycle_data[cycle_data['CATEGORY'] == 'WIND'],
                'hail': cycle_data[cycle_data['CATEGORY'] == 'HAIL']
            }
            
            cycle_dir = os.path.join(output_dir, f'cycle_{cycle:02d}z')
            os.makedirs(cycle_dir, exist_ok=True)
            
            for hazard, data in hazards.items():
                if len(data) > 0:
                    # Save shapefile
                    shp_path = os.path.join(cycle_dir, f'{hazard}_{date_str}_{cycle:02d}z.shp')
                    data.to_file(shp_path)
                    print(f"    Saved {hazard}: {len(data)} polygons")
                    
                    # Save GeoJSON too
                    json_path = shp_path.replace('.shp', '.geojson')
                    data.to_file(json_path, driver='GeoJSON')
                    
    return combined, cycles


def process_shapefiles_selective(zip_path, output_dir, date_str, hazard_types=None, 
                                output_formats=None, cycle_filter=None, outlook_type='convective'):
    """Extract and process shapefiles with selective options"""
    print("\nProcessing shapefiles...")
    
    # Default to all if not specified
    if not hazard_types:
        if outlook_type == 'fire':
            hazard_types = ['fire', 'dryt']
        else:
            hazard_types = ['categorical', 'tornado', 'wind', 'hail']
    if not output_formats:
        output_formats = ['shp', 'geojson']
    
    # Extract zip
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)
            
        # Load all shapefiles
        all_data = []
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f.endswith('.shp'):
                    shp_path = os.path.join(root, f)
                    gdf = gpd.read_file(shp_path)
                    all_data.append(gdf)
                    
        if not all_data:
            raise RuntimeError("No shapefiles found in archive")
            
        # Combine all
        combined = pd.concat(all_data, ignore_index=True)
        print(f"  Loaded {len(combined)} polygons")
        
        # Get unique cycles
        all_cycles = sorted(combined['CYCLE'].unique()) if 'CYCLE' in combined.columns else [0]
        print(f"  Found cycles: {all_cycles}")
        
        # Filter cycles if requested
        if cycle_filter:
            if cycle_filter == 'latest':
                cycles = [all_cycles[-1]]
                print(f"  Using latest cycle: {cycles[0]}Z")
            else:
                cycle_num = int(cycle_filter.replace('z', ''))
                cycles = [c for c in all_cycles if c == cycle_num]
                if not cycles:
                    print(f"  Warning: Cycle {cycle_filter} not found, using all cycles")
                    cycles = all_cycles
        else:
            cycles = all_cycles
        
        # Process each cycle
        for cycle in cycles:
            print(f"\n  Processing cycle {cycle}Z...")
            cycle_data = combined[combined['CYCLE'] == cycle] if 'CYCLE' in combined.columns else combined
            
            # Create cycle dir only if needed
            cycle_dir = None
            
            # Process requested hazard types
            hazards = {
                'categorical': cycle_data[cycle_data['CATEGORY'] == 'CATEGORICAL'],
                'tornado': cycle_data[cycle_data['CATEGORY'] == 'TORNADO'],
                'wind': cycle_data[cycle_data['CATEGORY'] == 'WIND'],
                'hail': cycle_data[cycle_data['CATEGORY'] == 'HAIL'],
                'fire': cycle_data[cycle_data['CATEGORY'].str.contains('FIRE', na=False)] if 'CATEGORY' in cycle_data.columns else cycle_data.iloc[0:0],
                'dryt': cycle_data[cycle_data['CATEGORY'].str.contains('DRY', na=False)] if 'CATEGORY' in cycle_data.columns else cycle_data.iloc[0:0],  # Dry thunderstorm
                'tstm': cycle_data[(cycle_data['CATEGORY'] == 'CATEGORICAL') & (cycle_data['THRESHOLD'] == 'TSTM')]  # Just thunderstorm areas
            }
            
            for hazard in hazard_types:
                data = hazards.get(hazard)
                if data is None or len(data) == 0:
                    continue
                
                # Create cycle dir on first use
                if cycle_dir is None:
                    cycle_dir = os.path.join(output_dir, f'cycle_{cycle:02d}z')
                    os.makedirs(cycle_dir, exist_ok=True)
                
                # Save in requested formats
                if 'shp' in output_formats:
                    shp_path = os.path.join(cycle_dir, f'{hazard}_{date_str}_{cycle:02d}z.shp')
                    data.to_file(shp_path)
                    print(f"    Saved {hazard}.shp: {len(data)} polygons")
                    
                if 'geojson' in output_formats:
                    json_path = os.path.join(cycle_dir, f'{hazard}_{date_str}_{cycle:02d}z.geojson')
                    data.to_file(json_path, driver='GeoJSON')
                    print(f"    Saved {hazard}.geojson")
                    
    return combined, cycles


def get_us_states():
    """Load US states boundaries"""
    try:
        # Try built-in Natural Earth data
        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        # Get North America countries
        na_countries = world[world['continent'] == 'North America']
        # Clip to US bounds
        us_bounds = [-130, 20, -65, 55]
        na_countries = na_countries.cx[us_bounds[0]:us_bounds[2], us_bounds[1]:us_bounds[3]]
        return na_countries
    except:
        pass
    
    # Alternative: Create a simple US outline
    try:
        from shapely.geometry import box
        us_outline = gpd.GeoDataFrame(
            {'name': ['US Bounds']}, 
            geometry=[box(-130, 20, -65, 55)],
            crs='EPSG:4326'
        )
        return us_outline
    except:
        print("  Warning: Could not load basemap")
        return None


def create_plots_selective(combined_data, cycles, output_dir, date_str, 
                          hazard_types=None, cycle_filter=None, outlook_type='convective'):
    """Generate PNG plots for selected hazard types and cycles"""
    print("\nGenerating plots...")
    
    # Default to all if not specified
    if not hazard_types:
        if outlook_type == 'fire':
            hazard_types = ['fire', 'dryt']
        else:
            hazard_types = ['categorical', 'tornado', 'wind', 'hail']
    
    # Get US states for basemap
    us_states = get_us_states()
    
    # Filter cycles if needed
    plot_cycles = cycles
    if cycle_filter:
        if cycle_filter == 'latest':
            plot_cycles = [cycles[-1]]
        else:
            cycle_num = int(cycle_filter.replace('z', ''))
            plot_cycles = [c for c in cycles if c == cycle_num]
            if not plot_cycles:
                plot_cycles = cycles
    
    for cycle in plot_cycles:
        print(f"\n  Plotting cycle {cycle}Z...")
        cycle_data = combined_data[combined_data['CYCLE'] == cycle] if 'CYCLE' in combined_data.columns else combined_data
        
        # Get issue time for title
        if 'PRODISS' in cycle_data.columns and len(cycle_data) > 0:
            prod = cycle_data.iloc[0]['PRODISS']
            issue_time = f"{prod[:4]}-{prod[4:6]}-{prod[6:8]} {prod[8:10]}:{prod[10:12]}Z"
        else:
            issue_time = f"Cycle {cycle}Z"
        
        # Create plots for requested hazards
        plot_configs = {
            'categorical': ('CATEGORICAL', 'Categorical Outlook'),
            'tornado': ('TORNADO', 'Tornado Probability'),
            'wind': ('WIND', 'Wind Probability'),
            'hail': ('HAIL', 'Hail Probability'),
            'fire': ('FIRE', 'Fire Weather Outlook'),
            'dryt': ('DRYT', 'Dry Thunderstorm Outlook'),
            'tstm': ('TSTM', 'General Thunderstorm Outlook')
        }
        
        cycle_dir = os.path.join(output_dir, f'cycle_{cycle:02d}z')
        
        for hazard_type in hazard_types:
            if hazard_type not in plot_configs:
                continue
                
            category, title = plot_configs[hazard_type]
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # Filter data
            if category == 'FIRE':
                plot_data = cycle_data[cycle_data['CATEGORY'].str.contains('FIRE', na=False)]
            elif category == 'DRY':
                plot_data = cycle_data[cycle_data['CATEGORY'].str.contains('DRY', na=False)]
            elif category == 'TSTM':
                plot_data = cycle_data[(cycle_data['CATEGORY'] == 'CATEGORICAL') & (cycle_data['THRESHOLD'] == 'TSTM')]
            else:
                plot_data = cycle_data[cycle_data['CATEGORY'] == category]
            
            # Plot US states basemap first
            if us_states is not None:
                us_states.boundary.plot(ax=ax, color='gray', linewidth=0.5, alpha=0.5)
            
            if len(plot_data) > 0:
                # Plot by threshold
                thresholds = sorted(plot_data['THRESHOLD'].unique())
                # Get appropriate colors
                if hazard_type in ['fire', 'dryt']:
                    colors = COLORS.get('fire', {})
                else:
                    colors = COLORS.get(hazard_type, {})
                
                for thresh in thresholds:
                    thresh_data = plot_data[plot_data['THRESHOLD'] == thresh]
                    color = colors.get(thresh, '#808080')
                    thresh_data.plot(ax=ax, color=color, alpha=0.7, edgecolor='black', label=thresh)
            else:
                ax.text(0.5, 0.5, f'No {title} Data', transform=ax.transAxes, 
                       ha='center', va='center', fontsize=20)
            
            # Map setup
            ax.set_xlim(-130, -65)
            ax.set_ylim(20, 55)
            ax.set_xlabel('Longitude')
            ax.set_ylabel('Latitude')
            ax.set_title(f'Day 1 {title}\n{issue_time}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Legend
            if len(plot_data) > 0:
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    # Create custom patches for legend
                    patches = []
                    for thresh in thresholds:
                        color = colors.get(thresh, '#808080')
                        patches.append(mpatches.Patch(color=color, label=thresh, alpha=0.7))
                    ax.legend(handles=patches, loc='upper right')
            
            # Save
            os.makedirs(cycle_dir, exist_ok=True)
            plot_path = os.path.join(cycle_dir, f'{hazard_type}_{date_str}_{cycle:02d}z.png')
            plt.tight_layout()
            plt.savefig(plot_path, dpi=200, bbox_inches='tight')
            plt.close()
            print(f"    Saved {hazard_type} plot")


def create_plots(combined_data, cycles, output_dir, date_str):
    """Generate PNG plots for each hazard type and cycle"""
    print("\nGenerating plots...")
    
    # Get US states for basemap
    us_states = get_us_states()
    
    for cycle in cycles:
        print(f"\n  Plotting cycle {cycle}Z...")
        cycle_data = combined_data[combined_data['CYCLE'] == cycle] if 'CYCLE' in combined_data.columns else combined_data
        
        # Get issue time for title
        if 'PRODISS' in cycle_data.columns and len(cycle_data) > 0:
            prod = cycle_data.iloc[0]['PRODISS']
            issue_time = f"{prod[:4]}-{prod[4:6]}-{prod[6:8]} {prod[8:10]}:{prod[10:12]}Z"
        else:
            issue_time = f"Cycle {cycle}Z"
        
        # Create plots
        plot_configs = [
            ('categorical', 'CATEGORICAL', 'Categorical Outlook'),
            ('tornado', 'TORNADO', 'Tornado Probability'),
            ('wind', 'WIND', 'Wind Probability'),
            ('hail', 'HAIL', 'Hail Probability')
        ]
        
        for plot_type, category, title in plot_configs:
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # Filter data
            if category == 'FIRE':
                plot_data = cycle_data[cycle_data['CATEGORY'].str.contains('FIRE', na=False)]
            elif category == 'DRY':
                plot_data = cycle_data[cycle_data['CATEGORY'].str.contains('DRY', na=False)]
            elif category == 'TSTM':
                plot_data = cycle_data[(cycle_data['CATEGORY'] == 'CATEGORICAL') & (cycle_data['THRESHOLD'] == 'TSTM')]
            else:
                plot_data = cycle_data[cycle_data['CATEGORY'] == category]
            
            # Plot US states basemap first
            if us_states is not None:
                us_states.boundary.plot(ax=ax, color='gray', linewidth=0.5, alpha=0.5)
            
            if len(plot_data) > 0:
                # Plot by threshold
                thresholds = sorted(plot_data['THRESHOLD'].unique())
                colors = COLORS.get(plot_type, {})
                
                for thresh in thresholds:
                    thresh_data = plot_data[plot_data['THRESHOLD'] == thresh]
                    color = colors.get(thresh, '#808080')
                    thresh_data.plot(ax=ax, color=color, alpha=0.7, edgecolor='black', label=thresh)
            else:
                ax.text(0.5, 0.5, f'No {title} Data', transform=ax.transAxes, 
                       ha='center', va='center', fontsize=20)
            
            # Map setup
            ax.set_xlim(-130, -65)
            ax.set_ylim(20, 55)
            ax.set_xlabel('Longitude')
            ax.set_ylabel('Latitude')
            ax.set_title(f'Day 1 {title}\n{issue_time}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Legend
            if len(plot_data) > 0:
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    # Create custom patches for legend
                    patches = []
                    for thresh in thresholds:
                        color = colors.get(thresh, '#808080')
                        patches.append(mpatches.Patch(color=color, label=thresh, alpha=0.7))
                    ax.legend(handles=patches, loc='upper right')
            
            # Save
            plot_path = os.path.join(output_dir, f'cycle_{cycle:02d}z', 
                                   f'{plot_type}_{date_str}_{cycle:02d}z.png')
            plt.tight_layout()
            plt.savefig(plot_path, dpi=200, bbox_inches='tight')
            plt.close()
            print(f"    Saved {plot_type} plot")


def create_html_map_selective(combined_data, cycles, output_dir, date_str,
                             hazard_types=None, cycle_filter=None, day=1, outlook_type='Convective'):
    """Create an interactive HTML map with selected hazards and cycles"""
    if not HAS_FOLIUM:
        print("\nSkipping HTML map (install folium: pip install folium)")
        return
        
    print("\nGenerating interactive HTML map...")
    
    # Default to all if not specified
    if not hazard_types:
        if outlook_type == 'fire':
            hazard_types = ['fire', 'dryt']
        else:
            hazard_types = ['categorical', 'tornado', 'wind', 'hail']
    
    # Create map
    m = folium.Map(location=[39, -98], zoom_start=4)
    
    # Get cycle to display
    if cycle_filter:
        if cycle_filter == 'latest':
            display_cycle = cycles[-1]
        else:
            cycle_num = int(cycle_filter.replace('z', ''))
            display_cycle = cycle_num if cycle_num in cycles else cycles[-1]
    else:
        display_cycle = cycles[-1]  # Default to latest
    
    cycle_data = combined_data[combined_data['CYCLE'] == display_cycle] if 'CYCLE' in combined_data.columns else combined_data
    
    # Add layers for requested hazard types
    hazard_configs = {
        'categorical': ('Categorical', 'CATEGORICAL', COLORS['categorical'], 0.6),
        'tornado': ('Tornado', 'TORNADO', COLORS['tornado'], 0.5),
        'wind': ('Wind', 'WIND', COLORS['wind'], 0.5),
        'hail': ('Hail', 'HAIL', COLORS['hail'], 0.5),
        'fire': ('Fire Weather', 'FIRE', COLORS['fire'], 0.6),
        'dryt': ('Dry Thunderstorm', 'DRYT', COLORS['fire'], 0.5),
        'tstm': ('Thunderstorm', 'TSTM', COLORS['categorical'], 0.5)
    }
    
    for hazard_type in hazard_types:
        if hazard_type not in hazard_configs:
            continue
            
        display_name, category, color_map, opacity = hazard_configs[hazard_type]
        fg = folium.FeatureGroup(name=display_name, show=(hazard_type == hazard_types[0]))
        
        # Filter data based on hazard type
        if category == 'FIRE':
            hazard_data = cycle_data[cycle_data['CATEGORY'].str.contains('FIRE', na=False)].copy()
        elif category == 'DRY':
            hazard_data = cycle_data[cycle_data['CATEGORY'].str.contains('DRY', na=False)].copy()
        elif category == 'TSTM':
            hazard_data = cycle_data[(cycle_data['CATEGORY'] == 'CATEGORICAL') & (cycle_data['THRESHOLD'] == 'TSTM')].copy()
        else:
            hazard_data = cycle_data[cycle_data['CATEGORY'] == category].copy()
        
        if len(hazard_data) > 0:
            # Sort data properly
            if category == 'CATEGORICAL':
                cat_order = ['TSTM', 'MRGL', 'SLGT', 'ENH', 'MDT', 'HIGH']
                hazard_data['sort_order'] = hazard_data['THRESHOLD'].map(
                    {cat: i for i, cat in enumerate(cat_order)}
                )
                hazard_data = hazard_data.sort_values('sort_order')
            else:
                # Handle numeric and SIGN thresholds
                def safe_float(x):
                    try:
                        return float(x)
                    except:
                        return 999.0  # Put SIGN last
                hazard_data['sort_order'] = hazard_data['THRESHOLD'].apply(safe_float)
                hazard_data = hazard_data.sort_values('sort_order')
            
            # Add polygons
            for _, row in hazard_data.iterrows():
                threshold = row['THRESHOLD']
                color = color_map.get(threshold, '#808080')
                
                # Create popup text
                popup_text = f"""
                <b>{display_name}</b><br>
                Threshold: {threshold}<br>
                Issued: {row.get('PRODISS', 'N/A')}<br>
                Valid: {row.get('VALID', 'N/A')} - {row.get('EXPIRE', 'N/A')}
                """
                
                folium.GeoJson(
                    row.geometry.__geo_interface__,
                    style_function=lambda x, color=color, opacity=opacity: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': opacity
                    },
                    tooltip=f"{display_name}: {threshold}",
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(fg)
        
        fg.add_to(m)
    
    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Add title
    title_html = f'''
    <div style="position: fixed; 
                top: 10px; left: 50px; width: 500px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <b>SPC Day {day} {outlook_type} Outlook - {date_str}</b><br>
    Showing: Cycle {display_cycle}Z<br>
    <small>Toggle layers using the control in upper right.<br>
    Click polygons for details. Data from Iowa Environmental Mesonet.</small>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Save map
    map_path = os.path.join(output_dir, f'interactive_map_{date_str}.html')
    m.save(map_path)
    print(f"  Saved interactive map: {map_path}")


def create_html_map(combined_data, cycles, output_dir, date_str):
    """Create an interactive HTML map using Folium"""
    if not HAS_FOLIUM:
        print("\nSkipping HTML map (install folium: pip install folium)")
        return
        
    print("\nGenerating interactive HTML map...")
    
    # Create separate HTML files for better organization
    # 1. Main map with just the latest cycle
    m = folium.Map(location=[39, -98], zoom_start=4)
    
    # Get latest cycle data
    latest_cycle = cycles[-1]
    cycle_data = combined_data[combined_data['CYCLE'] == latest_cycle] if 'CYCLE' in combined_data.columns else combined_data
    
    # Add base layers for each hazard type
    hazard_configs = [
        ('Categorical', 'CATEGORICAL', COLORS['categorical'], 0.6),
        ('Tornado', 'TORNADO', COLORS['tornado'], 0.5),
        ('Wind', 'WIND', COLORS['wind'], 0.5),
        ('Hail', 'HAIL', COLORS['hail'], 0.5)
    ]
    
    for display_name, category, color_map, opacity in hazard_configs:
        fg = folium.FeatureGroup(name=display_name, show=(display_name == 'Categorical'))
        
        hazard_data = cycle_data[cycle_data['CATEGORY'] == category].copy()
        
        if len(hazard_data) > 0:
            # Sort data properly
            if category == 'CATEGORICAL':
                cat_order = ['TSTM', 'MRGL', 'SLGT', 'ENH', 'MDT', 'HIGH']
                hazard_data['sort_order'] = hazard_data['THRESHOLD'].map(
                    {cat: i for i, cat in enumerate(cat_order)}
                )
                hazard_data = hazard_data.sort_values('sort_order')
            else:
                # Handle numeric and SIGN thresholds
                def safe_float(x):
                    try:
                        return float(x)
                    except:
                        return 999.0  # Put SIGN last
                hazard_data['sort_order'] = hazard_data['THRESHOLD'].apply(safe_float)
                hazard_data = hazard_data.sort_values('sort_order')
            
            # Add polygons
            for _, row in hazard_data.iterrows():
                threshold = row['THRESHOLD']
                color = color_map.get(threshold, '#808080')
                
                # Create popup text
                popup_text = f"""
                <b>{display_name}</b><br>
                Threshold: {threshold}<br>
                Issued: {row.get('PRODISS', 'N/A')}<br>
                Valid: {row.get('VALID', 'N/A')} - {row.get('EXPIRE', 'N/A')}
                """
                
                folium.GeoJson(
                    row.geometry.__geo_interface__,
                    style_function=lambda x, color=color, opacity=opacity: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': opacity
                    },
                    tooltip=f"{display_name}: {threshold}",
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(fg)
        
        fg.add_to(m)
    
    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Add title
    title_html = f'''
    <div style="position: fixed; 
                top: 10px; left: 50px; width: 500px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <b>SPC Day 1 Outlook - {date_str}</b><br>
    Latest Update: Cycle {latest_cycle}Z<br>
    <small>Toggle layers using the control in upper right.<br>
    Click polygons for details. Data from Iowa Environmental Mesonet.</small>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Save main map
    map_path = os.path.join(output_dir, f'interactive_map_{date_str}.html')
    m.save(map_path)
    print(f"  Saved interactive map: {map_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Download and process SPC outlooks (Day 1/2/3, Convective/Fire Weather)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Day 1 convective outlook (default)
  %(prog)s 2025-03-14
  
  # Day 2 outlook
  %(prog)s 2025-03-14 --day 2
  
  # Day 3 outlook, just categorical
  %(prog)s 2025-03-14 --day 3 --hazard categorical
  
  # Fire weather outlook
  %(prog)s 2025-03-14 --type fire
  
  # Only tornado shapefiles
  %(prog)s 2025-03-14 --hazard tornado --format shp
  
  # Multiple hazards and formats
  %(prog)s 2025-03-14 --hazard tornado,wind --format shp,png
        '''
    )
    parser.add_argument('date', help='Date to process (YYYY-MM-DD)')
    parser.add_argument('--output', '-o', default='./output', help='Output directory')
    parser.add_argument('--day', '-d', type=int, default=1, choices=[1, 2, 3],
                       help='Outlook day (1, 2, or 3; default: 1)')
    parser.add_argument('--type', '-t', default='convective', 
                       choices=['convective', 'fire'],
                       help='Outlook type (default: convective)')
    parser.add_argument('--hazard', '-H', 
                       help='Specific hazard types (comma-separated: categorical,tornado,wind,hail,fire)')
    parser.add_argument('--format', '-f',
                       help='Output formats (comma-separated: shp,geojson,png,html)')
    parser.add_argument('--cycle', '-c',
                       help='Specific cycle (01z,06z,13z,1630z,20z) or "latest" (16z is an alias for 1630z)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick mode - only download and extract, no processing')
    args = parser.parse_args()
    
    # Validate date
    try:
        datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        print("Error: Date must be YYYY-MM-DD format")
        sys.exit(1)
    
    # Parse options
    hazard_types = None
    if args.hazard:
        hazard_types = [h.strip().lower() for h in args.hazard.split(',')]
        if args.type == 'fire':
            valid_hazards = ['fire', 'dryt']  # fire categories and dry thunderstorm
        else:
            valid_hazards = ['categorical', 'tornado', 'wind', 'hail', 'tstm']  # Added tstm
        for h in hazard_types:
            if h not in valid_hazards:
                print(f"Error: Invalid hazard type '{h}' for {args.type} outlook. Choose from: {', '.join(valid_hazards)}")
                sys.exit(1)
    
    output_formats = None
    if args.format:
        output_formats = [f.strip().lower() for f in args.format.split(',')]
        valid_formats = ['shp', 'geojson', 'png', 'html']
        for f in output_formats:
            if f not in valid_formats:
                print(f"Error: Invalid format '{f}'. Choose from: {', '.join(valid_formats)}")
                sys.exit(1)
    
    cycle_filter = args.cycle.lower() if args.cycle else None
    if cycle_filter and cycle_filter != 'latest':
        # Validate cycle format
        try:
            cycle_num = int(cycle_filter.replace('z', ''))
            # Allow 16z as an alias for 1630z
            if cycle_num == 16:
                cycle_num = 1630
                cycle_filter = '1630z'
            
            valid_cycles = [1, 6, 13, 1630, 20]
            if cycle_num not in valid_cycles:
                print(f"Error: Invalid cycle. Choose from: 01z, 06z, 13z, 1630z, 20z, latest")
                sys.exit(1)
        except:
            print(f"Error: Invalid cycle format. Use: 01z, 06z, 13z, 1630z, 20z, or latest")
            sys.exit(1)
    
    # Create output dir
    outlook_type_code = 'F' if args.type == 'fire' else 'C'
    output_subdir = f"{args.date}_day{args.day}_{args.type}"
    output_dir = os.path.join(args.output, output_subdir)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"SPC Outlook Tool")
    print(f"================")
    print(f"Date: {args.date}")
    print(f"Day: {args.day}")
    print(f"Type: {args.type.title()}")
    print(f"Output: {output_dir}")
    
    try:
        # Download data
        zip_path = fetch_outlook_data(args.date, output_dir, day=args.day, 
                                    outlook_type=outlook_type_code)
        
        # Quick mode - just download
        if args.quick:
            print("\n✓ Quick mode - data downloaded")
            return
        
        # Process shapefiles
        combined_data, cycles = process_shapefiles_selective(
            zip_path, output_dir, args.date, hazard_types, output_formats, cycle_filter, args.type
        )
        
        # Create plots if requested
        if not output_formats or 'png' in output_formats:
            create_plots_selective(combined_data, cycles, output_dir, args.date, 
                                 hazard_types, cycle_filter, args.type)
        
        # Create HTML map if requested
        if not output_formats or 'html' in output_formats:
            create_html_map_selective(combined_data, cycles, output_dir, args.date,
                                    hazard_types, cycle_filter, args.day, args.type.title())
        
        print(f"\n✓ Complete! Generated {len(cycles)} cycles x 4 hazard types")
        print(f"  Output directory: {output_dir}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()