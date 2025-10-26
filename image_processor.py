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
            'dtm': True,  # Digital Terrain Model
            'orthophoto-resolution': 5,  # cm/pixel
            'min-num-features': 10000,
            'use-3dmesh': True,
            'mesh-octree-depth': 11,
            'ignore-gsd': False,
            'matcher-neighbors': 8,
            'auto-boundary': True
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
        print(f"Command: {' '.join(cmd)}")

        try:
            # Run with real-time output
            result = subprocess.run(cmd, text=True)
            if result.returncode == 0:
                print("\nOpenDroneMap processing completed successfully!")
                return True
            else:
                print(f"\nOpenDroneMap processing failed with return code: {result.returncode}")
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
        """Generate a simple HTML map showing photo locations"""
        gps_images = [img for img in image_info if img['gps']]

        if not gps_images:
            return

        # Calculate center point
        avg_lat = sum(img['gps']['latitude'] for img in gps_images) / len(gps_images)
        avg_lon = sum(img['gps']['longitude'] for img in gps_images) / len(gps_images)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Drone Photo Coverage Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <style>
        #map {{ height: 600px; width: 100%; }}
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <h1>Drone Mapping Coverage - {len(gps_images)} Photos</h1>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([{avg_lat}, {avg_lon}], 17);

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);

        var photos = {json.dumps([{
            'lat': img['gps']['latitude'],
            'lon': img['gps']['longitude'],
            'name': img['filename']
        } for img in gps_images])};

        photos.forEach(function(photo) {{
            L.circleMarker([photo.lat, photo.lon], {{
                radius: 5,
                fillColor: "#ff7800",
                color: "#000",
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }}).addTo(map).bindPopup(photo.name);
        }});

        // Fit map to show all markers
        var group = L.featureGroup(photos.map(p => L.marker([p.lat, p.lon])));
        map.fitBounds(group.getBounds().pad(0.1));
    </script>
</body>
</html>"""

        map_file = self.report_dir / "coverage_map.html"
        with open(map_file, 'w') as f:
            f.write(html_content)

        print(f"  Coverage map saved to: {map_file}")

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