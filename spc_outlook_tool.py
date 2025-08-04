#!/usr/bin/env python3
"""
SPC Outlook Tool - Downloads and processes SPC outlooks from IEM.
Supports Day 1/2/3 convective, thunderstorm, and fire weather outlooks.
Generates shapefiles, GeoJSON, PNG images, and interactive HTML maps.
"""
import os
import sys
import io
import json
import zipfile
import tempfile
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Third-party dependencies (install with pip)
try:
    import requests
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import Point
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError as e:
    print(f"Error: Missing dependency - {e.name}. Please install it using 'pip install {e.name}'")
    sys.exit(1)

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

# --- Configuration ---

# Setup logging
log = logging.getLogger(__name__)

class SPCOutlookTool:
    """
    A tool to download, process, and visualize SPC convective outlooks.
    """
    BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/spc_outlooks.py"
    COLORS = {
        'categorical': {
            'TSTM': '#40E0D0', 'MRGL': '#66FF66', 'SLGT': '#FFD700',
            'ENH': '#FF8C00', 'MDT': '#FF0000', 'HIGH': '#FF00FF'
        },
        'tornado': {
            '0.02': '#006600', '0.05': '#228B22', '0.10': '#FFFF00',
            '0.15': '#FFA500', '0.30': '#FF0000', '0.45': '#FF00FF',
            '0.60': '#912CEE', 'SIGN': '#FF00FF'
        },
        'wind': {
            '0.05': '#8B4513', '0.15': '#FFD700', '0.30': '#FF0000',
            '0.45': '#FF00FF', '0.60': '#912CEE', 'SIGN': '#FF00FF'
        },
        'hail': {
            '0.05': '#8B4513', '0.15': '#FFD700', '0.30': '#FF0000',
            '0.45': '#FF00FF', '0.60': '#912CEE', 'SIGN': '#FF00FF'
        },
        'fire': {
            'ELEV': '#FFA500', 'CRIT': '#FF0000', 'EXTM': '#FF00FF',
            'ISODRYT': '#8B4513', 'DRYT': '#D2691E', 'SCTDRYT': '#DEB887'
        }
    }

    def __init__(self, args):
        self.args = args
        self.setup_logging()

    def setup_logging(self):
        """Configures the logging format and level."""
        level = logging.DEBUG if self.args.verbose else logging.INFO
        logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    def run(self):
        """Main execution flow."""
        log.info(f"Starting SPC Outlook Tool for {self.args.date}")
        
        output_type_code = 'F' if self.args.type == 'fire' else 'C'
        output_subdir = f"{self.args.date}_day{self.args.day}_{self.args.type}"
        output_dir = Path(self.args.output) / output_subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        log.info(f"Output will be saved to: {output_dir}")

        try:
            zip_path = self.fetch_outlook_data(output_dir, output_type_code)
            if self.args.quick:
                log.info("Quick mode enabled. Download complete.")
                return

            combined_data, cycles = self.process_shapefiles(zip_path, output_dir)
            
            if not self.args.format or 'png' in self.args.format:
                self.create_plots(combined_data, cycles, output_dir)
            
            if HAS_FOLIUM and (not self.args.format or 'html' in self.args.format):
                self.create_html_map(combined_data, cycles, output_dir)
            elif not HAS_FOLIUM and (not self.args.format or 'html' in self.args.format):
                log.warning("Folium not found. Skipping interactive map. Install with 'pip install folium'")

            log.info(f"✓ Successfully processed {len(cycles)} cycles.")

        except Exception as e:
            log.error(f"An error occurred: {e}", exc_info=self.args.verbose)
            sys.exit(1)

    def fetch_outlook_data(self, output_dir, outlook_type):
        """Downloads outlook data from the IEM archive."""
        log.info(f"Fetching Day {self.args.day} {self.args.type.title()} outlook...")
        dt = datetime.strptime(self.args.date, '%Y-%m-%d')
        start_utc = dt.strftime('%Y-%m-%dT00:00Z')
        end_utc = (dt + timedelta(days=1)).strftime('%Y-%m-%dT00:00Z')
        
        params = {'d': str(self.args.day), 'type': outlook_type, 'sts': start_utc, 'ets': end_utc}
        
        for geom in [None, 'lyr', 'nolyr']:
            if geom:
                params['geom'] = geom
            log.debug(f"Trying geometry: {geom or 'default'}")
            try:
                r = requests.get(self.BASE_URL, params=params, timeout=60)
                if r.status_code == 200 and r.content:
                    zip_path = output_dir / f"raw_data_day{self.args.day}_{self.args.date}.zip"
                    with open(zip_path, 'wb') as f:
                        f.write(r.content)
                    log.info(f"Success! Downloaded {len(r.content)/1024:.1f} KB")
                    return zip_path
            except requests.RequestException as e:
                log.warning(f"Request failed: {e}")
        
        raise RuntimeError("Could not fetch data from IEM. The service may be down or the date is invalid.")

    def process_shapefiles(self, zip_path, output_dir):
        """Extracts and processes shapefiles, normalizing cycle data."""
        log.info("Processing shapefiles...")
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(tmpdir)
            
            all_files = list(Path(tmpdir).rglob('*.shp'))
            if not all_files:
                raise RuntimeError("No shapefiles found in the downloaded archive.")

            all_data = pd.concat([gpd.read_file(f) for f in all_files], ignore_index=True)
            log.info(f"Loaded {len(all_data)} polygons from {len(all_files)} shapefiles.")

            if 'CYCLE' in all_data.columns:
                all_data['CYCLE'] = all_data['CYCLE'].replace(-1, 20)
                all_cycles = sorted(all_data['CYCLE'].unique())
            else:
                all_cycles = [0] # For outlooks without cycle info
            log.info(f"Found cycles: {all_cycles}")

            cycles_to_process = self._filter_cycles(all_cycles)

            for cycle in cycles_to_process:
                self._process_single_cycle(all_data, cycle, output_dir)
        
        return all_data, cycles_to_process

    def _filter_cycles(self, all_cycles):
        """Filters cycles based on user input."""
        if not self.args.cycle or self.args.cycle == 'all':
            return all_cycles
        if self.args.cycle == 'latest':
            log.info("Filtering for the latest cycle.")
            return [all_cycles[-1]]
        
        try:
            cycle_num = int(self.args.cycle.replace('z', ''))
            mapped_cycle = 16 if cycle_num == 1630 else cycle_num
            if mapped_cycle in all_cycles:
                log.info(f"Filtering for cycle {self.args.cycle}.")
                return [mapped_cycle]
            else:
                log.warning(f"Cycle {self.args.cycle} not found. Processing all available cycles.")
                return all_cycles
        except ValueError:
            log.error(f"Invalid cycle format: {self.args.cycle}. Processing all cycles.")
            return all_cycles

    def _process_single_cycle(self, all_data, cycle, output_dir):
        """Saves shapefiles and GeoJSON for a single cycle."""
        cycle_str = '1630z' if cycle == 16 else f"{cycle:02d}z"
        log.info(f"Processing cycle {cycle_str}...")
        cycle_data = all_data[all_data['CYCLE'] == cycle] if 'CYCLE' in all_data.columns else all_data
        cycle_dir = output_dir / f"cycle_{cycle_str}"
        cycle_dir.mkdir(exist_ok=True)

        hazards = self._get_hazard_types()
        for hazard in hazards:
            data = self._filter_hazard_data(cycle_data, hazard)
            if not data.empty:
                if not self.args.format or 'shp' in self.args.format:
                    shp_path = cycle_dir / f'{hazard}_{self.args.date}_{cycle_str}.shp'
                    data.to_file(shp_path)
                    log.debug(f"Saved {hazard}.shp: {len(data)} polygons")
                if not self.args.format or 'geojson' in self.args.format:
                    json_path = cycle_dir / f'{hazard}_{self.args.date}_{cycle_str}.geojson'
                    data.to_file(json_path, driver='GeoJSON')
                    log.debug(f"Saved {hazard}.geojson")

    def _get_hazard_types(self):
        """Returns a list of hazard types based on user args or defaults."""
        if self.args.hazard:
            return [h.strip().lower() for h in self.args.hazard.split(',')]
        return ['categorical', 'tornado', 'wind', 'hail'] if self.args.type == 'convective' else ['fire', 'dryt']

    def _filter_hazard_data(self, cycle_data, hazard):
        """Filters GeoDataFrame for a specific hazard type."""
        if hazard == 'fire':
            return cycle_data[cycle_data['CATEGORY'].str.contains('FIRE', na=False)]
        if hazard == 'dryt':
            return cycle_data[cycle_data['CATEGORY'].str.contains('DRY', na=False)]
        if hazard == 'tstm':
            return cycle_data[(cycle_data['CATEGORY'] == 'CATEGORICAL') & (cycle_data['THRESHOLD'] == 'TSTM')]
        return cycle_data[cycle_data['CATEGORY'] == hazard.upper()]

    def create_plots(self, combined_data, cycles, output_dir):
        """Generates PNG plots for specified hazards and cycles."""
        log.info("Generating plots...")
        us_states = self._get_us_states_basemap()
        
        for cycle in cycles:
            cycle_str = '1630z' if cycle == 16 else f"{cycle:02d}z"
            log.info(f"Plotting cycle {cycle_str}...")
            cycle_data = combined_data[combined_data['CYCLE'] == cycle] if 'CYCLE' in combined_data.columns else combined_data
            cycle_dir = output_dir / f"cycle_{cycle_str}"
            cycle_dir.mkdir(exist_ok=True)

            for hazard_type in self._get_hazard_types():
                self._create_single_plot(cycle_data, hazard_type, cycle_str, cycle_dir, us_states)

    def _create_single_plot(self, cycle_data, hazard_type, cycle_str, cycle_dir, us_states):
        """Creates and saves a single PNG plot."""
        plot_data = self._filter_hazard_data(cycle_data, hazard_type)
        title = f"Day {self.args.day} {hazard_type.title()} Outlook ({cycle_str})"
        
        fig, ax = plt.subplots(figsize=(12, 8))
        if us_states is not None:
            us_states.boundary.plot(ax=ax, color='gray', linewidth=0.5, alpha=0.5)

        if not plot_data.empty:
            colors = self.COLORS.get(hazard_type, {})
            if hazard_type in ['fire', 'dryt']:
                colors = self.COLORS.get('fire', {})

            patches = []
            for thresh in sorted(plot_data['THRESHOLD'].unique()):
                thresh_data = plot_data[plot_data['THRESHOLD'] == thresh]
                color = colors.get(thresh, '#808080')
                thresh_data.plot(ax=ax, color=color, alpha=0.7, edgecolor='black')
                patches.append(mpatches.Patch(color=color, label=thresh, alpha=0.7))
            if patches:
                ax.legend(handles=patches, loc='upper right')
        else:
            ax.text(0.5, 0.5, f'No {hazard_type.title()} Data', transform=ax.transAxes, ha='center', va='center', fontsize=20)

        ax.set(xlim=(-130, -65), ylim=(20, 55), xlabel='Longitude', ylabel='Latitude', title=title)
        ax.grid(True, alpha=0.3)
        
        plot_path = cycle_dir / f'{hazard_type}_{self.args.date}_{cycle_str}.png'
        plt.tight_layout()
        plt.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close()
        log.debug(f"Saved plot: {plot_path}")

    def create_html_map(self, combined_data, cycles, output_dir):
        """Creates an interactive HTML map."""
        log.info("Generating interactive HTML map...")
        display_cycle = self._filter_cycles(cycles)[-1] # Use latest from filtered cycles
        cycle_str = '1630Z' if display_cycle == 16 else f"{display_cycle}Z"
        cycle_data = combined_data[combined_data['CYCLE'] == display_cycle]

        m = folium.Map(location=[39, -98], zoom_start=4)

        for hazard_type in self._get_hazard_types():
            self._add_map_layer(m, cycle_data, hazard_type)

        folium.LayerControl(collapsed=False).add_to(m)
        self._add_map_title(m, cycle_str)
        
        map_path = output_dir / f'interactive_map_{self.args.date}.html'
        m.save(str(map_path))
        log.info(f"Saved interactive map: {map_path}")

    def _add_map_layer(self, m, cycle_data, hazard_type):
        """Adds a GeoJSON layer to a Folium map."""
        hazard_data = self._filter_hazard_data(cycle_data, hazard_type)
        if hazard_data.empty:
            return

        display_name = hazard_type.title()
        colors = self.COLORS.get(hazard_type, {})
        if hazard_type in ['fire', 'dryt']:
            colors = self.COLORS.get('fire', {})

        fg = folium.FeatureGroup(name=display_name, show=(hazard_type == self._get_hazard_types()[0]))
        
        for _, row in hazard_data.iterrows():
            threshold = row['THRESHOLD']
            color = colors.get(threshold, '#808080')
            popup_text = f"<b>{display_name}</b><br>Threshold: {threshold}"
            
            folium.GeoJson(
                row.geometry,
                style_function=lambda x, c=color: {'fillColor': c, 'color': 'black', 'weight': 1, 'fillOpacity': 0.6},
                tooltip=f"{display_name}: {threshold}",
                popup=folium.Popup(popup_text, max_width=300)
            ).add_to(fg)
        fg.add_to(m)

    def _add_map_title(self, m, cycle_str):
        """Adds a title overlay to the Folium map."""
        title_html = f'''
        <div style="position: fixed; top: 10px; left: 50px; width: 450px;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px;">
        <b>SPC Day {self.args.day} {self.args.type.title()} Outlook - {self.args.date}</b><br>
        Showing Cycle: {cycle_str}<br>
        <small>Toggle layers in the upper right. Click polygons for details.</small>
        </div>'''
        m.get_root().html.add_child(folium.Element(title_html))

    def _get_us_states_basemap(self):
        """Loads US states boundaries for the plot basemap."""
        try:
            world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
            return world[world['continent'] == 'North America'].cx[-130:-65, 20:55]
        except Exception as e:
            log.warning(f"Could not load basemap. Plots will not have state outlines. Details: {e}")
            return None

def main():
    """Parses command-line arguments and runs the tool."""
    parser = argparse.ArgumentParser(
        description='Download and process SPC Convective Outlooks.',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
Examples:
  # Get the latest Day 1 outlook for today
  %(prog)s $(date -u +%%Y-%%m-%%d)

  # Get a specific cycle for a past date and save as PNG and GeoJSON
  %(prog)s 2025-03-14 --cycle 1630z --format png,geojson

  # Get the Day 2 fire weather outlook
  %(prog)s 2025-07-21 --day 2 --type fire

  # Get only tornado outlooks in shapefile format
  %(prog)s 2025-03-14 --hazard tornado --format shp

  # See more detailed output for debugging
  %(prog)s 2025-03-14 --verbose
'''
    )
    parser.add_argument('date', help='Date for the outlook (YYYY-MM-DD). UTC is assumed.')
    parser.add_argument('--output', '-o', default='./output', help='Root directory to save output files.')
    parser.add_argument('--day', '-d', type=int, default=1, choices=[1, 2, 3], help='Outlook day (1, 2, or 3).')
    parser.add_argument('--type', '-t', default='convective', choices=['convective', 'fire'], help='Outlook type.')
    parser.add_argument('--hazard', '-H', help='Comma-separated list of hazard types to process (e.g., tornado,hail).')
    parser.add_argument('--format', '-f', help='Comma-separated list of output formats (shp,geojson,png,html).')
    parser.add_argument('--cycle', '-c', help='Specific cycle to process (e.g., 01z, 13z, 1630z) or "latest" or "all".')
    parser.add_argument('--quick', action='store_true', help='Only download the raw data and exit.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable detailed debug logging.')
    
    args = parser.parse_args()

    try:
        tool = SPCOutlookTool(args)
        tool.run()
    except Exception as e:
        log.error(f"A critical error occurred: {e}", exc_info=args.verbose)
        sys.exit(1)

if __name__ == '__main__':
    main()
