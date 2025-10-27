#!/usr/bin/env python3
"""
Image Processing Pipeline for Drone Mapping
Processes drone photos into orthomosaics and 3D models
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from datetime import datetime
import exifread
import piexif

class ImageProcessor:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.processed_dir = self.output_dir / "processed_images"
        self.georef_dir = self.output_dir / "georeferenced"
        self.ortho_dir = self.output_dir / "orthomosaic"
        self.report_dir = self.output_dir / "reports"

        for dir in [self.processed_dir, self.georef_dir,
                   self.ortho_dir, self.report_dir]:
            dir.mkdir(parents=True, exist_ok=True)

    def extract_gps_from_exif(self, image_path: str) -> Optional[Dict]:
        """Extract GPS coordinates from image EXIF data"""
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f)

            # Extract GPS data
            gps_data = {}
            gps_keys = ['GPS GPSLatitude', 'GPS GPSLatitudeRef',
                       'GPS GPSLongitude', 'GPS GPSLongitudeRef',
                       'GPS GPSAltitude', 'GPS GPSAltitudeRef']

            for key in gps_keys:
                if key in tags:
                    gps_data[key] = tags[key]

            if not gps_data:
                return None

            # Convert GPS coordinates to decimal degrees
            def convert_to_degrees(value):
                d = float(value.values[0].num) / float(value.values[0].den)
                m = float(value.values[1].num) / float(value.values[1].den)
                s = float(value.values[2].num) / float(value.values[2].den)
                return d + (m / 60.0) + (s / 3600.0)

            lat = convert_to_degrees(gps_data['GPS GPSLatitude'])
            if gps_data['GPS GPSLatitudeRef'].values != 'N':
                lat = -lat

            lon = convert_to_degrees(gps_data['GPS GPSLongitude'])
            if gps_data['GPS GPSLongitudeRef'].values != 'E':
                lon = -lon

            # Extract altitude if available
            alt = None
            if 'GPS GPSAltitude' in gps_data:
                alt_value = gps_data['GPS GPSAltitude'].values[0]
                alt = float(alt_value.num) / float(alt_value.den)

            return {
                'latitude': lat,
                'longitude': lon,
                'altitude': alt
            }

        except Exception as e:
            print(f"Error extracting GPS from {image_path}: {e}")
            return None

    def prepare_images(self) -> List[Dict]:
        """Prepare images for processing and extract metadata"""
        image_info = []
        image_extensions = ['.jpg', '.jpeg', '.png', '.tif', '.tiff']

        print("Scanning for images...")
        for image_path in self.input_dir.iterdir():
            if image_path.suffix.lower() in image_extensions:
                gps_data = self.extract_gps_from_exif(str(image_path))

                info = {
                    'filename': image_path.name,
                    'path': str(image_path),
                    'gps': gps_data
                }

                image_info.append(info)

                # Copy to processed directory
                shutil.copy2(image_path, self.processed_dir / image_path.name)

        print(f"Found {len(image_info)} images")
        if gps_enabled := sum(1 for img in image_info if img['gps']):
            print(f"  - {gps_enabled} images with GPS data")

        return image_info

    def create_odm_project(self, project_name: str) -> Path:
        """Create OpenDroneMap project structure"""
        odm_project = self.output_dir / "odm_project" / project_name
        odm_images = odm_project / "images"
        odm_images.mkdir(parents=True, exist_ok=True)

        # Copy processed images to ODM project
        for image in self.processed_dir.iterdir():
            shutil.copy2(image, odm_images / image.name)

        return odm_project

    def run_opendronemap(self, project_path: Path, options: Dict = None) -> bool:
        """
        Run OpenDroneMap processing via Docker
        Note: Requires Docker and opendronemap/odm image
        """
        default_options = {
            'dsm': True,  # Digital Surface Model
            'dtm': False,  # Skip DTM for speed
            'orthophoto-resolution': 10,  # Reduced resolution for speed
            'min-num-features': 4000,  # Significantly reduced for 700+ images
            'feature-quality': 'medium',  # Medium quality (faster)
            'pc-quality': 'medium',  # Medium point cloud quality
            'use-3dmesh': False,  # Skip 3D mesh for speed
            'fast-orthophoto': True,  # Use fast orthophoto generation
            'ignore-gsd': False,
            'matcher-neighbors': 6,  # Reduced from 8
            'auto-boundary': True,
            # Memory optimization for large datasets (700+ images)
            'split': 250,  # Larger groups (fewer merges)
            'split-overlap': 100,  # Reduced overlap
            'max-concurrency': 2,  # Limit parallel processes
            'optimize-disk-space': True  # Clean up intermediate files
        }

        if options:
            default_options.update(options)

        # Get absolute path for Docker volume mounting
        project_abs_path = project_path.resolve()
        project_parent = project_abs_path.parent
        project_name = project_abs_path.name

        # Build ODM Docker command
        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{project_parent}:/datasets',
            'opendronemap/odm',
            '--project-path', '/datasets',
            project_name
        ]

        for key, value in default_options.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f'--{key}')
            else:
                cmd.extend([f'--{key}', str(value)])

        print(f"Running OpenDroneMap via Docker...")
        print(f"Project: {project_name}")
        print(f"Command: {' '.join(cmd)}\n")
        print("=" * 60)
        print("ODM PROCESSING OUTPUT (this may take 1-3 hours)")
        print("=" * 60)

        try:
            # Run with real-time output streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Stream output in real-time
            for line in process.stdout:
                print(line, end='')

            # Wait for completion
            process.wait()

            if process.returncode == 0:
                print("\n" + "=" * 60)
                print("OpenDroneMap processing completed successfully!")
                print("=" * 60)
                return True
            else:
                print("\n" + "=" * 60)
                print(f"OpenDroneMap processing failed with return code: {process.returncode}")
                print("=" * 60)
                return False
        except FileNotFoundError:
            print("Docker not found. Please install Docker first.")
            print("Visit: https://www.docker.com/get-started")
            return False
        except Exception as e:
            print(f"Error running OpenDroneMap: {e}")
            return False

    def create_simple_mosaic(self, image_list: List[str]) -> bool:
        """
        Create a simple mosaic using ImageMagick (fallback option)
        Note: This is much simpler than proper photogrammetry
        """
        print("Creating simple mosaic with ImageMagick...")

        try:
            # Check if ImageMagick is installed (v7 uses 'magick' command)
            subprocess.run(['magick', '--version'],
                         capture_output=True, check=True)

            # Limit number of images for mosaic (too many can cause memory issues)
            max_images = 100
            if len(image_list) > max_images:
                print(f"Using first {max_images} images for mosaic (out of {len(image_list)} total)")
                image_list = image_list[:max_images]

            # Create mosaic using montage (part of ImageMagick)
            output_file = self.ortho_dir / "simple_mosaic.jpg"
            cmd = ['magick', 'montage'] + image_list + [
                '-tile', '10x10',
                '-geometry', '200x200+2+2>',  # Resize to max 200x200 pixels, keep aspect ratio
                '-background', 'white',
                '-quality', '85',
                str(output_file)
            ]

            print(f"Creating mosaic from {len(image_list)} images...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Simple mosaic created: {output_file}")
                return True
            else:
                print(f"ImageMagick error: {result.stderr}")
                return False

        except (FileNotFoundError, subprocess.CalledProcessError):
            print("ImageMagick not found or failed.")
            print("Install with: brew install imagemagick")
            return False

    def generate_report(self, image_info: List[Dict], processing_success: bool):
        """Generate processing report"""
        report = {
            'processing_date': datetime.now().isoformat(),
            'input_directory': str(self.input_dir),
            'output_directory': str(self.output_dir),
            'total_images': len(image_info),
            'images_with_gps': sum(1 for img in image_info if img['gps']),
            'processing_success': processing_success,
            'images': image_info
        }

        report_file = self.report_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nProcessing Report:")
        print(f"  Total images: {report['total_images']}")
        print(f"  Images with GPS: {report['images_with_gps']}")
        print(f"  Report saved to: {report_file}")

        # Generate coverage map if GPS data available
        if report['images_with_gps'] > 0:
            self.generate_coverage_map(image_info)

    def generate_coverage_map(self, image_info: List[Dict]):
        """Generate an interactive HTML map showing all photo locations"""
        gps_images = [img for img in image_info if img['gps']]

        if not gps_images:
            return

        # Calculate center point and bounds
        avg_lat = sum(img['gps']['latitude'] for img in gps_images) / len(gps_images)
        avg_lon = sum(img['gps']['longitude'] for img in gps_images) / len(gps_images)

        # Calculate min/max for bounds
        lats = [img['gps']['latitude'] for img in gps_images]
        lons = [img['gps']['longitude'] for img in gps_images]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Drone Photo Coverage Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: relative;
            z-index: 1000;
        }}
        .header h1 {{
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 8px;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 12px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #f8f9fa;
            padding: 8px 16px;
            border-radius: 6px;
            border-left: 3px solid #ff6b35;
        }}
        .stat-label {{
            font-size: 11px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-value {{
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
            margin-top: 2px;
        }}
        #map {{
            height: calc(100vh - 160px);
            width: 100%;
        }}
        .leaflet-popup-content {{
            font-size: 13px;
            line-height: 1.5;
        }}
        .photo-popup {{
            font-family: monospace;
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🗺️ Drone Mapping Coverage</h1>
        <div class="stats">
            <div class="stat">
                <div class="stat-label">Total Photos</div>
                <div class="stat-value">{len(gps_images)}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Coverage Area</div>
                <div class="stat-value">{abs(max_lat - min_lat) * 111000:.0f}m × {abs(max_lon - min_lon) * 111000 * abs(avg_lat / 90):.0f}m</div>
            </div>
            <div class="stat">
                <div class="stat-label">Center Point</div>
                <div class="stat-value">{avg_lat:.6f}, {avg_lon:.6f}</div>
            </div>
        </div>
    </div>
    <div id="map"></div>
    <script>
        // Initialize map
        var map = L.map('map', {{
            zoomControl: true,
            attributionControl: true
        }});

        // Add OpenStreetMap tile layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }}).addTo(map);

        // Photo data
        var photos = {json.dumps([{
            'lat': img['gps']['latitude'],
            'lon': img['gps']['longitude'],
            'alt': img['gps'].get('altitude'),
            'name': img['filename']
        } for img in gps_images])};

        // Add markers for each photo
        var markers = [];
        photos.forEach(function(photo, index) {{
            var marker = L.circleMarker([photo.lat, photo.lon], {{
                radius: 6,
                fillColor: '#ff6b35',
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.85
            }});

            // Create popup content
            var popupContent = '<div class="photo-popup">';
            popupContent += '<strong>Photo #' + (index + 1) + '</strong><br>';
            popupContent += photo.name + '<br>';
            popupContent += 'Lat: ' + photo.lat.toFixed(6) + '<br>';
            popupContent += 'Lon: ' + photo.lon.toFixed(6);
            if (photo.alt) {{
                popupContent += '<br>Alt: ' + photo.alt.toFixed(1) + 'm';
            }}
            popupContent += '</div>';

            marker.bindPopup(popupContent);
            marker.addTo(map);
            markers.push(marker);
        }});

        // Fit map to show all markers with padding
        var bounds = L.latLngBounds(photos.map(p => [p.lat, p.lon]));
        map.fitBounds(bounds, {{ padding: [50, 50] }});

        // Add scale control
        L.control.scale({{ imperial: true, metric: true }}).addTo(map);

        console.log('Coverage map loaded: ' + photos.length + ' photos');
    </script>
</body>
</html>"""

        map_file = self.report_dir / "coverage_map.html"
        with open(map_file, 'w') as f:
            f.write(html_content)

        print(f"  Coverage map saved to: {map_file}")
        print(f"  Open with: open {map_file}")

def main():
    parser = argparse.ArgumentParser(description="Process drone images into maps")
    parser.add_argument("input_dir", help="Directory containing drone photos")
    parser.add_argument("--output", default="mapping_output",
                       help="Output directory for processed data")
    parser.add_argument("--use-odm", action="store_true",
                       help="Use OpenDroneMap for processing (requires installation)")
    parser.add_argument("--simple-mosaic", action="store_true",
                       help="Create simple mosaic using ImageMagick")

    args = parser.parse_args()

    processor = ImageProcessor(args.input_dir, args.output)

    # Prepare images and extract metadata
    image_info = processor.prepare_images()

    if not image_info:
        print("No images found to process!")
        return

    processing_success = False

    # Try OpenDroneMap if requested
    if args.use_odm:
        project_name = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        odm_project = processor.create_odm_project(project_name)
        processing_success = processor.run_opendronemap(odm_project)

    # Fallback to simple mosaic if requested
    elif args.simple_mosaic:
        image_list = [str(processor.processed_dir / img['filename'])
                     for img in image_info]
        processing_success = processor.create_simple_mosaic(image_list)

    # Generate report
    processor.generate_report(image_info, processing_success)

if __name__ == "__main__":
    main()