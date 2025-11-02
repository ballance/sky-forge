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

        # Progress tracking
        self.progress_file = self.output_dir / "processing_progress.json"
        self.odm_stages = [
            'dataset', 'opensfm', 'mve', 'odm_filterpoints', 'odm_meshing',
            'mvs_texturing', 'odm_georeferencing', 'odm_dem', 'odm_orthophoto'
        ]

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

    def load_progress(self) -> Dict:
        """Load processing progress from file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'status': 'not_started',
            'current_stage': None,
            'completed_stages': [],
            'start_time': None,
            'last_update': None,
            'estimated_completion': None
        }

    def save_progress(self, progress: Dict):
        """Save processing progress to file"""
        progress['last_update'] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

    def estimate_stage_progress(self, current_stage: str, log_line: str) -> float:
        """Estimate progress within current ODM stage"""
        # Stage weights (approximate time percentages)
        stage_weights = {
            'dataset': 5,
            'opensfm': 40,  # Feature detection/matching - longest stage
            'mve': 10,
            'odm_filterpoints': 5,
            'odm_meshing': 10,
            'mvs_texturing': 10,
            'odm_georeferencing': 5,
            'odm_dem': 10,
            'odm_orthophoto': 5
        }

        total_weight = sum(stage_weights.values())
        completed_weight = sum(stage_weights.get(s, 0) for s in self.odm_stages
                              if s in self.load_progress().get('completed_stages', []))

        # Current stage progress indicators
        current_stage_weight = stage_weights.get(current_stage, 5)
        stage_progress = 0.0

        if 'detect_features' in log_line or 'Extracting features' in log_line:
            stage_progress = 0.2
        elif 'match_features' in log_line or 'Matching features' in log_line:
            stage_progress = 0.5
        elif 'reconstruction' in log_line or 'Reconstructing' in log_line:
            stage_progress = 0.7
        elif 'completed' in log_line.lower() or 'finished' in log_line.lower():
            stage_progress = 1.0

        current_contribution = current_stage_weight * stage_progress
        overall_progress = (completed_weight + current_contribution) / total_weight

        return min(100.0, overall_progress * 100)

    def create_odm_project(self, project_name: str, resume: bool = False) -> Path:
        """Create OpenDroneMap project structure"""
        odm_project = self.output_dir / "odm_project" / project_name
        odm_images = odm_project / "images"

        # Check if project already exists (resume scenario)
        if resume and odm_project.exists():
            print(f"📂 Resuming existing ODM project: {project_name}")
            existing_images = list(odm_images.glob('*')) if odm_images.exists() else []
            print(f"   Found {len(existing_images)} existing images")
            return odm_project

        odm_images.mkdir(parents=True, exist_ok=True)

        # Copy processed images to ODM project
        print("📋 Preparing images for ODM...")
        image_count = 0
        for image in self.processed_dir.iterdir():
            if image.is_file():
                shutil.copy2(image, odm_images / image.name)
                image_count += 1
        print(f"   Copied {image_count} images to project")

        return odm_project

    def run_opendronemap(self, project_path: Path, options: Dict = None, resume: bool = False) -> bool:
        """
        Run OpenDroneMap processing via Docker
        Note: Requires Docker and opendronemap/odm image
        """
        # Count images to determine optimal settings
        images_dir = project_path / "images"
        image_count = len(list(images_dir.glob('*'))) if images_dir.exists() else 0

        print(f"📊 Dataset: {image_count} images")

        # Adaptive settings based on dataset size
        if image_count < 300:
            # Small dataset: don't use split, better quality
            print("   Using optimized settings for small dataset (no split processing)")
            default_options = {
                'dsm': True,
                'dtm': False,
                'orthophoto-resolution': 5,  # Better resolution
                'min-num-features': 8000,  # More features for quality
                'feature-quality': 'high',
                'pc-quality': 'medium',
                'use-3dmesh': False,
                'fast-orthophoto': True,
                'ignore-gsd': False,
                'matcher-neighbors': 8,
                'auto-boundary': True,
                'max-concurrency': 4,
                'optimize-disk-space': False  # Keep files for debugging
            }
        elif image_count < 500:
            # Medium dataset: conservative split
            print("   Using optimized settings for medium dataset (split=100)")
            default_options = {
                'dsm': True,
                'dtm': False,
                'orthophoto-resolution': 8,
                'min-num-features': 6000,
                'feature-quality': 'medium',
                'pc-quality': 'medium',
                'use-3dmesh': False,
                'fast-orthophoto': True,
                'ignore-gsd': False,
                'matcher-neighbors': 8,
                'auto-boundary': True,
                'split': 100,
                'split-overlap': 150,
                'max-concurrency': 3,
                'optimize-disk-space': True
            }
        else:
            # Large dataset: aggressive split
            print("   Using optimized settings for large dataset (split=200)")
            default_options = {
                'dsm': True,
                'dtm': False,
                'orthophoto-resolution': 10,
                'min-num-features': 4000,
                'feature-quality': 'medium',
                'pc-quality': 'medium',
                'use-3dmesh': False,
                'fast-orthophoto': True,
                'ignore-gsd': False,
                'matcher-neighbors': 6,
                'auto-boundary': True,
                'split': 200,
                'split-overlap': 100,
                'max-concurrency': 2,
                'optimize-disk-space': True
            }

        if options:
            default_options.update(options)

        # Add rerun-from option for resume functionality
        if resume:
            default_options['rerun-from'] = 'odm_orthophoto'  # Will auto-detect last completed stage

        # Get absolute path for Docker volume mounting
        project_abs_path = project_path.resolve()
        project_parent = project_abs_path.parent
        project_name = project_abs_path.name

        # Load progress
        progress = self.load_progress()
        if not progress.get('start_time'):
            progress['start_time'] = datetime.now().isoformat()
            progress['status'] = 'running'

        # Check for existing outputs to determine resume point
        if resume:
            existing_stages = self.detect_completed_stages(project_path)
            progress['completed_stages'] = existing_stages
            if existing_stages:
                print(f"🔄 Resuming from last checkpoint...")
                print(f"   Completed stages: {', '.join(existing_stages)}")

        self.save_progress(progress)

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

        print(f"\n{'='*60}")
        print(f"🚀 Running OpenDroneMap via Docker")
        print(f"{'='*60}")
        print(f"Project: {project_name}")
        if resume:
            print(f"Mode: RESUME (will continue from last checkpoint)")
        else:
            print(f"Mode: NEW (starting from scratch)")
        print(f"\nCommand: {' '.join(cmd)}\n")
        print("=" * 60)
        print("ODM PROCESSING OUTPUT")
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

            current_stage = None
            last_progress_update = datetime.now()

            # Stream output in real-time with progress tracking
            for line in process.stdout:
                print(line, end='')

                # Detect current stage
                for stage in self.odm_stages:
                    if stage in line.lower() or f"running {stage}" in line.lower():
                        if current_stage != stage:
                            current_stage = stage
                            progress['current_stage'] = stage
                            if stage not in progress['completed_stages']:
                                print(f"\n{'='*60}")
                                print(f"📍 Stage: {stage}")
                                print(f"{'='*60}")
                        break

                # Update progress every 30 seconds
                if (datetime.now() - last_progress_update).seconds >= 30:
                    if current_stage:
                        overall_progress = self.estimate_stage_progress(current_stage, line)
                        progress['estimated_completion'] = overall_progress
                        self.save_progress(progress)
                        print(f"\n⏱️  Overall Progress: {overall_progress:.1f}%")
                    last_progress_update = datetime.now()

                # Detect completed stages
                if 'running' in line.lower() and current_stage:
                    if current_stage not in progress['completed_stages']:
                        progress['completed_stages'].append(current_stage)
                        self.save_progress(progress)

            # Wait for completion
            process.wait()

            if process.returncode == 0:
                progress['status'] = 'completed'
                progress['estimated_completion'] = 100.0
                progress['completion_time'] = datetime.now().isoformat()
                self.save_progress(progress)

                print("\n" + "=" * 60)
                print("✅ OpenDroneMap processing completed successfully!")
                print("=" * 60)
                self.print_output_summary(project_path)

                # Generate web tiles and viewer
                self.create_web_outputs(project_path)

                return True
            else:
                progress['status'] = 'failed'
                progress['error_code'] = process.returncode
                self.save_progress(progress)

                print("\n" + "=" * 60)
                print(f"❌ OpenDroneMap processing failed with return code: {process.returncode}")
                print("=" * 60)
                print("\n💡 To resume processing, run the same command with --resume flag")
                return False

        except KeyboardInterrupt:
            progress['status'] = 'interrupted'
            self.save_progress(progress)
            print("\n\n" + "=" * 60)
            print("⚠️  Processing interrupted by user")
            print("=" * 60)
            print("\n💡 To resume processing, run the same command with --resume flag")
            return False

        except FileNotFoundError:
            print("Docker not found. Please install Docker first.")
            print("Visit: https://www.docker.com/get-started")
            return False
        except Exception as e:
            progress['status'] = 'error'
            progress['error_message'] = str(e)
            self.save_progress(progress)
            print(f"Error running OpenDroneMap: {e}")
            return False

    def detect_completed_stages(self, project_path: Path) -> List[str]:
        """Detect which ODM stages have already been completed"""
        completed = []

        # Check for stage-specific output directories/files
        stage_markers = {
            'dataset': project_path / 'images',
            'opensfm': project_path / 'opensfm' / 'reconstruction.json',
            'odm_filterpoints': project_path / 'odm_filterpoints',
            'odm_meshing': project_path / 'odm_meshing',
            'odm_texturing': project_path / 'odm_texturing',
            'odm_georeferencing': project_path / 'odm_georeferencing',
            'odm_dem': project_path / 'odm_dem',
            'odm_orthophoto': project_path / 'odm_orthophoto' / 'odm_orthophoto.tif'
        }

        for stage, marker in stage_markers.items():
            if marker.exists():
                completed.append(stage)

        return completed

    def print_output_summary(self, project_path: Path):
        """Print summary of generated outputs"""
        print("\n📦 Generated Outputs:")

        outputs = {
            'Orthophoto': project_path / 'odm_orthophoto' / 'odm_orthophoto.tif',
            'Digital Surface Model': project_path / 'odm_dem' / 'dsm.tif',
            'Digital Terrain Model': project_path / 'odm_dem' / 'dtm.tif',
            '3D Model': project_path / 'odm_texturing' / 'odm_textured_model.obj',
            'Point Cloud': project_path / 'entwine_pointcloud' / 'ept.json'
        }

        for name, path in outputs.items():
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"   ✅ {name}: {path} ({size_mb:.1f} MB)")
            else:
                print(f"   ⚪ {name}: Not generated")

    def print_progress_summary(self):
        """Print current processing progress"""
        progress = self.load_progress()

        print("\n" + "=" * 60)
        print("📊 Processing Progress Summary")
        print("=" * 60)

        status = progress.get('status', 'unknown')
        status_emoji = {
            'not_started': '⚪',
            'running': '🔄',
            'completed': '✅',
            'failed': '❌',
            'interrupted': '⚠️',
            'error': '❌'
        }

        print(f"\nStatus: {status_emoji.get(status, '❓')} {status.upper()}")

        if progress.get('current_stage'):
            print(f"Current Stage: {progress['current_stage']}")

        if progress.get('completed_stages'):
            print(f"\nCompleted Stages ({len(progress['completed_stages'])}/{len(self.odm_stages)}):")
            for stage in progress['completed_stages']:
                print(f"   ✅ {stage}")

        if progress.get('estimated_completion'):
            completion = progress['estimated_completion']
            bar_length = 40
            filled = int(bar_length * completion / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\nOverall Progress: [{bar}] {completion:.1f}%")

        if progress.get('start_time'):
            start = datetime.fromisoformat(progress['start_time'])
            elapsed = datetime.now() - start
            print(f"\nElapsed Time: {elapsed.seconds // 3600}h {(elapsed.seconds % 3600) // 60}m")

        print("=" * 60)

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

    def create_web_outputs(self, project_path: Path) -> bool:
        """
        Create web-ready outputs after successful ODM processing
        Generates tiles and HTML viewers
        """
        orthophoto_path = project_path / 'odm_orthophoto' / 'odm_orthophoto.tif'

        if not orthophoto_path.exists():
            print("\n⚠️  No orthophoto found, skipping web output generation")
            return False

        print("\n" + "=" * 60)
        print("🌐 Generating Web Outputs")
        print("=" * 60)

        # Generate map tiles
        tiles_dir = self.output_dir / "tiles"
        tiles_success = self.generate_tiles_from_geotiff(orthophoto_path, tiles_dir)

        if tiles_success:
            # Create tiled viewer
            self.create_tiled_viewer(tiles_dir)

            # Create web deployment package
            self.create_web_package(tiles_dir, orthophoto_path)

            print("\n" + "=" * 60)
            print("✅ Web outputs created successfully!")
            print("=" * 60)
            print(f"\n📂 Outputs:")
            print(f"   Tiles:         {tiles_dir}")
            print(f"   Tiled Viewer:  {self.output_dir / 'tiled_viewer.html'}")
            print(f"   Web Package:   {self.output_dir / 'web_package'}")
            print(f"\n🌐 To view locally:")
            print(f"   open {self.output_dir / 'tiled_viewer.html'}")
            print(f"\n📦 To deploy to web server:")
            print(f"   Upload the 'web_package' folder to your server")

            return True

        return False

    def generate_tiles_from_geotiff(self, geotiff_path: Path, output_dir: Path = None) -> bool:
        """
        Generate web map tiles from GeoTIFF using gdal2tiles
        Creates XYZ tile pyramid for fast web viewing
        """
        if not geotiff_path.exists():
            print(f"❌ GeoTIFF not found: {geotiff_path}")
            return False

        if output_dir is None:
            output_dir = self.output_dir / "tiles"

        output_dir.mkdir(parents=True, exist_ok=True)

        print("\n" + "="*60)
        print("🗺️  Generating Map Tiles")
        print("="*60)
        print(f"Source: {geotiff_path}")
        print(f"Output: {output_dir}")

        try:
            # Check if gdal2tiles.py is available
            # Try different possible locations
            gdal2tiles_commands = [
                ['gdal2tiles.py'],
                ['python3', '-m', 'gdal2tiles'],
                ['python', '-m', 'gdal2tiles'],
            ]

            gdal2tiles_cmd = None
            for cmd in gdal2tiles_commands:
                try:
                    result = subprocess.run(
                        cmd + ['--help'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 or 'gdal2tiles' in result.stdout.lower():
                        gdal2tiles_cmd = cmd
                        break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue

            if not gdal2tiles_cmd:
                print("❌ gdal2tiles.py not found!")
                print("\nTo install GDAL:")
                print("  macOS:  brew install gdal")
                print("  Ubuntu: sudo apt-get install gdal-bin python3-gdal")
                print("  pip:    pip install gdal")
                return False

            # Generate tiles with optimal settings for web viewing
            # -z: zoom levels (auto calculates optimal range)
            # -w: web viewer (generates simple HTML viewer)
            # --processes: parallel processing for speed
            cmd = gdal2tiles_cmd + [
                '-z', '10-22',  # Zoom levels (10=regional, 22=very detailed)
                '-w', 'none',   # Don't generate default viewer (we'll make our own)
                '--processes=4',  # Parallel processing
                '-r', 'lanczos',  # High-quality resampling
                '--xyz',  # XYZ tile scheme (standard web tiles)
                str(geotiff_path),
                str(output_dir)
            ]

            print(f"\nCommand: {' '.join(cmd)}")
            print("\n⏳ Generating tiles (this may take a few minutes)...\n")

            # Run with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            for line in process.stdout:
                # Filter out excessive progress messages
                if '%' in line or 'Processing' in line:
                    print(line, end='', flush=True)
                else:
                    print(line, end='')

            process.wait()

            if process.returncode == 0:
                print("\n✅ Tiles generated successfully!")

                # Count generated tiles
                tile_count = sum(1 for _ in output_dir.rglob('*.png'))
                print(f"   Generated {tile_count:,} tiles")

                # Estimate tile directory size
                total_size = sum(f.stat().st_size for f in output_dir.rglob('*.png'))
                size_mb = total_size / (1024 * 1024)
                print(f"   Total size: {size_mb:.1f} MB")

                return True
            else:
                print(f"\n❌ Tile generation failed with return code: {process.returncode}")
                return False

        except Exception as e:
            print(f"❌ Error generating tiles: {e}")
            import traceback
            traceback.print_exc()
            return False

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

    def create_tiled_viewer(self, tiles_dir: Path) -> Path:
        """Create interactive HTML viewer for tiled orthomosaic"""

        # Get mission name from output directory
        mission_name = self.output_dir.parent.name if self.output_dir.parent.name != 'outputs' else 'Orthomosaic'

        # Calculate approximate bounds from tiles directory structure
        # Parse tilemapresource.xml if exists, otherwise use default
        bounds_center = [0, 0]
        bounds_zoom = 15

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{mission_name} - Tiled Orthomosaic Viewer</title>

    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #1a1a1a;
            color: #ffffff;
        }}

        #header {{
            background: #2d2d2d;
            padding: 15px 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }}

        #header h1 {{
            font-size: 24px;
            font-weight: 600;
            color: #4CAF50;
        }}

        .badge {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        #mission-info {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 14px;
        }}

        .info-item {{
            background: #3d3d3d;
            padding: 5px 12px;
            border-radius: 4px;
        }}

        .info-label {{
            color: #999;
            margin-right: 5px;
        }}

        .info-value {{
            color: #fff;
            font-weight: 500;
        }}

        #map {{
            width: 100%;
            height: calc(100vh - 80px);
        }}

        #coordinates {{
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: rgba(45, 45, 45, 0.95);
            padding: 10px 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}

        .controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .btn {{
            background: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s;
        }}

        .btn:hover {{
            background: #45a049;
        }}

        .btn-secondary {{
            background: #555;
        }}

        .btn-secondary:hover {{
            background: #666;
        }}

        #opacity-control {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        #opacity-slider {{
            width: 150px;
        }}

        .leaflet-control-attribution {{
            background: rgba(45, 45, 45, 0.9) !important;
            color: #999 !important;
        }}

        .leaflet-control-attribution a {{
            color: #4CAF50 !important;
        }}

        /* Performance indicator */
        #perf-indicator {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(76, 175, 80, 0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
    </style>
</head>
<body>
    <div id="header">
        <div style="display: flex; align-items: center; gap: 10px;">
            <h1>🗺️ {mission_name}</h1>
            <span class="badge">Tiled</span>
        </div>
        <div id="mission-info">
            <div class="info-item">
                <span class="info-label">Mode:</span>
                <span class="info-value">Fast Tile Loading</span>
            </div>
        </div>
        <div class="controls">
            <div id="opacity-control">
                <label for="opacity-slider">Opacity:</label>
                <input type="range" id="opacity-slider" min="0" max="100" value="100">
                <span id="opacity-value">100%</span>
            </div>
            <button class="btn btn-secondary" onclick="resetView()">Reset View</button>
        </div>
    </div>

    <div id="perf-indicator">⚡ Fast Tiles</div>
    <div id="map"></div>

    <div id="coordinates">
        <div>Lat: <span id="lat">--</span></div>
        <div>Lon: <span id="lon">--</span></div>
        <div>Zoom: <span id="zoom">--</span></div>
    </div>

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <script>
        // Initialize map
        const map = L.map('map', {{
            center: {bounds_center},
            zoom: {bounds_zoom},
            zoomControl: true,
            attributionControl: true,
            maxZoom: 22
        }});

        // Add base layer (OpenStreetMap)
        const baseLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }}).addTo(map);

        // Add orthomosaic tile layer
        const orthomosaicLayer = L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Orthomosaic © Drone Mapping',
            maxZoom: 22,
            tms: false,  // XYZ tile scheme (not TMS)
            opacity: 1.0
        }}).addTo(map);

        let initialBounds = null;

        // Update coordinate display
        map.on('mousemove', function(e) {{
            document.getElementById('lat').textContent = e.latlng.lat.toFixed(6);
            document.getElementById('lon').textContent = e.latlng.lng.toFixed(6);
        }});

        map.on('zoomend', function() {{
            document.getElementById('zoom').textContent = map.getZoom();
        }});

        // Opacity control
        const opacitySlider = document.getElementById('opacity-slider');
        const opacityValue = document.getElementById('opacity-value');

        opacitySlider.addEventListener('input', function() {{
            const opacity = this.value / 100;
            opacityValue.textContent = this.value + '%';
            orthomosaicLayer.setOpacity(opacity);
        }});

        // Reset view function
        function resetView() {{
            if (initialBounds) {{
                map.fitBounds(initialBounds);
            }} else {{
                map.setView({bounds_center}, {bounds_zoom});
            }}
        }}

        // Try to auto-detect bounds from first loaded tiles
        let boundsDetected = false;
        orthomosaicLayer.on('tileload', function(e) {{
            if (!boundsDetected) {{
                // Get current map bounds as initial bounds
                initialBounds = map.getBounds();
                boundsDetected = true;
            }}
        }});

        // Set initial zoom display
        document.getElementById('zoom').textContent = map.getZoom();

        console.log('Tiled viewer loaded successfully!');
        console.log('Tile URL pattern: tiles/{{z}}/{{x}}/{{y}}.png');
    </script>
</body>
</html>'''

        viewer_file = self.output_dir / "tiled_viewer.html"
        with open(viewer_file, 'w') as f:
            f.write(html_content)

        print(f"\n✅ Tiled viewer created: {viewer_file}")
        return viewer_file

    def create_web_package(self, tiles_dir: Path, orthophoto_path: Path) -> Path:
        """Create deployment-ready web package with tiles"""
        web_package_dir = self.output_dir / "web_package"
        web_package_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📦 Creating web deployment package...")

        # Copy tiles to web package
        package_tiles_dir = web_package_dir / "tiles"
        if package_tiles_dir.exists():
            shutil.rmtree(package_tiles_dir)

        print(f"   Copying tiles...")
        shutil.copytree(tiles_dir, package_tiles_dir)

        # Create index.html (tiled viewer)
        mission_name = self.output_dir.parent.name if self.output_dir.parent.name != 'outputs' else 'Orthomosaic'

        index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{mission_name} - Orthomosaic Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
        #map {{ width: 100%; height: 100vh; }}
        #info {{
            position: absolute;
            top: 10px;
            left: 60px;
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 1000;
        }}
        #info h2 {{ margin: 0 0 10px 0; font-size: 18px; color: #333; }}
        #info p {{ margin: 5px 0; font-size: 14px; color: #666; }}
        .badge {{ background: #4CAF50; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
    </style>
</head>
<body>
    <div id="info">
        <h2>🗺️ {mission_name}</h2>
        <p><span class="badge">Interactive Map</span></p>
    </div>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map').setView([0, 0], 15);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }}).addTo(map);
        L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Orthomosaic © Drone Mapping',
            maxZoom: 22,
            opacity: 1.0
        }}).addTo(map);
        L.control.scale({{ imperial: true, metric: true }}).addTo(map);
    </script>
</body>
</html>'''

        with open(web_package_dir / "index.html", 'w') as f:
            f.write(index_html)

        # Create README
        readme_content = f'''# {mission_name} - Web Deployment Package

## Contents

- `index.html` - Interactive map viewer
- `tiles/` - Map tiles (XYZ format)

## Deployment Instructions

### Option 1: Simple Web Server

Upload this entire folder to any web server. No backend required!

### Option 2: Local Testing

```bash
# Python 3
python3 -m http.server 8000

# Python 2
python -m SimpleHTTPServer 8000
```

Then open: http://localhost:8000

### Option 3: Static Hosting

Upload to:
- GitHub Pages
- Netlify
- Vercel
- AWS S3 + CloudFront
- Any static hosting service

## File Size

Total tiles: {sum(1 for _ in package_tiles_dir.rglob('*.png')):,} files
Total size: {sum(f.stat().st_size for f in package_tiles_dir.rglob('*.png')) / (1024*1024):.1f} MB

## Performance

✅ Fast loading - only loads visible tiles
✅ No backend required - 100% client-side
✅ Mobile-friendly responsive design
✅ Works offline after initial load

---

Generated by Drone Mapping Utility Suite
'''

        with open(web_package_dir / "README.md", 'w') as f:
            f.write(readme_content)

        print(f"   ✅ Web package created: {web_package_dir}")
        print(f"   📄 Files: index.html, tiles/, README.md")

        return web_package_dir

def main():
    parser = argparse.ArgumentParser(description="Process drone images into maps")
    parser.add_argument("input_dir", nargs='?', help="Directory containing drone photos")
    parser.add_argument("--output", default="mapping_output",
                       help="Output directory for processed data")
    parser.add_argument("--use-odm", action="store_true",
                       help="Use OpenDroneMap for processing (requires installation)")
    parser.add_argument("--simple-mosaic", action="store_true",
                       help="Create simple mosaic using ImageMagick")
    parser.add_argument("--resume", action="store_true",
                       help="Resume interrupted ODM processing")
    parser.add_argument("--progress", action="store_true",
                       help="Show current processing progress")
    parser.add_argument("--generate-tiles", type=str, metavar="GEOTIFF_PATH",
                       help="Generate web tiles from existing GeoTIFF orthomosaic")

    args = parser.parse_args()

    # If just checking progress, show it and exit
    if args.progress:
        if not Path(args.output).exists():
            print("Error: Output directory does not exist")
            return
        processor = ImageProcessor(".", args.output)  # Dummy input_dir
        processor.print_progress_summary()
        return

    # If generating tiles from existing GeoTIFF
    if args.generate_tiles:
        geotiff_path = Path(args.generate_tiles)
        if not geotiff_path.exists():
            print(f"Error: GeoTIFF not found: {geotiff_path}")
            return
        processor = ImageProcessor(".", args.output)  # Dummy input_dir
        tiles_success = processor.generate_tiles_from_geotiff(geotiff_path)
        if tiles_success:
            processor.create_tiled_viewer(processor.output_dir / "tiles")
            processor.create_web_package(processor.output_dir / "tiles", geotiff_path)
            print("\n✅ Tile generation complete!")
        return

    if not args.input_dir:
        parser.error("input_dir is required unless using --progress or --generate-tiles")

    processor = ImageProcessor(args.input_dir, args.output)

    # Prepare images and extract metadata
    image_info = processor.prepare_images()

    if not image_info:
        print("No images found to process!")
        return

    processing_success = False

    # Try OpenDroneMap if requested
    if args.use_odm:
        # Determine project name - use existing if resuming
        if args.resume:
            # Find existing project
            odm_projects_dir = processor.output_dir / "odm_project"
            if odm_projects_dir.exists():
                existing_projects = list(odm_projects_dir.iterdir())
                if existing_projects:
                    project_name = existing_projects[-1].name  # Use most recent
                    print(f"Found existing project: {project_name}")
                else:
                    print("Warning: --resume specified but no existing projects found")
                    project_name = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            else:
                print("Warning: --resume specified but no existing projects found")
                project_name = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            project_name = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        odm_project = processor.create_odm_project(project_name, resume=args.resume)
        processing_success = processor.run_opendronemap(odm_project, resume=args.resume)

    # Fallback to simple mosaic if requested
    elif args.simple_mosaic:
        image_list = [str(processor.processed_dir / img['filename'])
                     for img in image_info]
        processing_success = processor.create_simple_mosaic(image_list)

    # Generate report
    processor.generate_report(image_info, processing_success)

if __name__ == "__main__":
    main()