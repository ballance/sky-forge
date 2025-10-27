#!/usr/bin/env python3
"""
Mission Control Center for Drone Mapping
Central command interface for all mapping operations
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import subprocess
from typing import Dict, List, Optional

class MissionControl:
    def __init__(self, mission_name: str = None, drone_profile: str = None, area_m2: int = None):
        self.mission_name = mission_name or f"Mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.mission_dir = Path(f"missions/{self.mission_name}")
        self.mission_dir.mkdir(parents=True, exist_ok=True)

        # Create mission subdirectories
        self.plans_dir = self.mission_dir / "flight_plans"
        self.images_dir = self.mission_dir / "captured_images"
        self.outputs_dir = self.mission_dir / "outputs"
        self.logs_dir = self.mission_dir / "logs"

        for dir in [self.plans_dir, self.images_dir, self.outputs_dir, self.logs_dir]:
            dir.mkdir(parents=True, exist_ok=True)

        self.config = self.load_or_create_config(drone_profile, area_m2)

    def load_or_create_config(self, drone_profile: str = None, area_m2: int = None) -> Dict:
        """Load or create mission configuration"""
        config_file = self.mission_dir / "mission_config.json"

        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)

        # Default configuration - generic mapping mission
        config = {
            'mission_name': self.mission_name,
            'mission_type': 'area_mapping',
            'estimated_area_m2': area_m2 or 160000,  # Default ~40 acres
            'estimated_area_acres': round((area_m2 or 160000) / 4047, 1),
            'drone_profile': drone_profile or 'potensic_atom_2',
            'mapping_parameters': {
                'altitude_m': 70,
                'forward_overlap': 70,
                'side_overlap': 60,
                'gsd_target_cm': 2.0
            },
            'safety_parameters': {
                'max_wind_speed_ms': 10,
                'min_battery_percent': 30,
                'max_flight_time_min': 25
            },
            'processing_options': {
                'generate_orthomosaic': True,
                'generate_3d_model': False,
                'generate_dsm': True,
                'output_format': 'GeoTIFF'
            }
        }

        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        return config

    def run_preflight_checks(self, lat: float, lon: float) -> bool:
        """Run comprehensive preflight checks"""
        print("\n" + "="*60)
        print("🚁 RUNNING PREFLIGHT CHECKS")
        print("="*60)

        cmd = [
            sys.executable,
            'preflight_checklist.py',
            '--lat', str(lat),
            '--lon', str(lon)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)

            # Check for errors in output
            if "NO GO" in result.stdout:
                print("\n❌ Preflight checks failed. Resolve issues before proceeding.")
                return False

            return True

        except Exception as e:
            print(f"Error running preflight checks: {e}")
            return False

    def generate_flight_plan(self, center_lat: float, center_lon: float,
                           area_size: float = None) -> str:
        """Generate optimized flight plan"""
        print("\n" + "="*60)
        print("📍 GENERATING FLIGHT PLAN")
        print("="*60)

        # Calculate area_size from config if not provided
        if area_size is None:
            area_m2 = self.config.get('estimated_area_m2', 160000)
            area_size = int((area_m2 ** 0.5))  # Square root for side length

        output_file = self.plans_dir / f"flight_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        cmd = [
            sys.executable,
            'flight_planner.py',
            '--drone', self.config.get('drone_profile', 'potensic_atom_2'),
            '--center-lat', str(center_lat),
            '--center-lon', str(center_lon),
            '--area-size', str(area_size),
            '--altitude', str(self.config['mapping_parameters']['altitude_m']),
            '--output', str(output_file)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)

            if output_file.exists():
                print(f"\n✅ Flight plan saved to: {output_file}")
                return str(output_file)
            else:
                print("\n❌ Failed to generate flight plan")
                return None

        except Exception as e:
            print(f"Error generating flight plan: {e}")
            return None

    def monitor_odm_processing(self):
        """Monitor active OpenDroneMap Docker container"""
        print("\n" + "="*60)
        print("👀 MONITORING ODM PROCESSING")
        print("="*60)

        try:
            # Find running ODM container
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'ancestor=opendronemap/odm', '--format', '{{.ID}} {{.Names}}'],
                capture_output=True,
                text=True
            )

            if not result.stdout.strip():
                print("❌ No active ODM containers found")
                print("\nTip: Start processing first with:")
                print(f"  python mission_control.py --mission {self.mission_name} --action process --use-odm")
                return

            container_id = result.stdout.strip().split()[0]
            container_name = result.stdout.strip().split()[1] if len(result.stdout.strip().split()) > 1 else container_id

            print(f"✅ Found ODM container: {container_name} ({container_id[:12]})")
            print("\nStreaming logs (Ctrl+C to stop)...\n")
            print("="*60)

            # Tail the logs
            subprocess.run(['docker', 'logs', '-f', container_id])

        except KeyboardInterrupt:
            print("\n\n" + "="*60)
            print("Stopped monitoring (container still running)")
            print("="*60)
        except Exception as e:
            print(f"Error monitoring container: {e}")

    def process_images(self, use_odm: bool = False) -> bool:
        """Process captured images into maps"""
        print("\n" + "="*60)
        print("🗺️  PROCESSING IMAGES")
        print("="*60)

        if not any(self.images_dir.iterdir()):
            print("❌ No images found in capture directory")
            print(f"   Please place images in: {self.images_dir}")
            return False

        cmd = [
            sys.executable,
            'image_processor.py',
            str(self.images_dir),
            '--output', str(self.outputs_dir)
        ]

        if use_odm:
            cmd.append('--use-odm')
        else:
            cmd.append('--simple-mosaic')

        try:
            # Stream output in real-time instead of capturing it
            result = subprocess.run(cmd, text=True)
            return result.returncode == 0

        except Exception as e:
            print(f"Error processing images: {e}")
            return False

    def estimate_mission_stats(self) -> Dict:
        """Estimate mission statistics based on area and drone specs"""
        # Get total area from config
        total_area = self.config.get('estimated_area_m2', 160000)

        # Calculate based on drone capabilities
        from flight_planner import DroneSpecs, MappingParams, FlightPlanner

        drone_profile = self.config.get('drone_profile', 'potensic_atom_2')
        drone = DroneSpecs.from_profile(drone_profile)
        params = MappingParams(altitude=self.config['mapping_parameters']['altitude_m'])
        planner = FlightPlanner(drone, params)

        # Calculate coverage
        image_width, image_height = planner.calculate_footprint()
        area_per_image = image_width * image_height

        forward_overlap = self.config['mapping_parameters']['forward_overlap'] / 100
        side_overlap = self.config['mapping_parameters']['side_overlap'] / 100
        effective_area_per_image = area_per_image * (1 - forward_overlap) * (1 - side_overlap)

        total_images = int(total_area / effective_area_per_image * 1.2)  # 20% safety margin

        # Time estimation
        photo_time = total_images * 2  # 2 seconds per photo
        flight_distance = (total_area ** 0.5) * 20  # Rough estimate
        flight_time = flight_distance / drone.cruise_speed
        total_time = (photo_time + flight_time) / 60  # Convert to minutes

        batteries_needed = int(total_time / (drone.max_flight_time * 0.8)) + 1

        stats = {
            'drone_name': drone.name,
            'drone_profile': drone_profile,
            'estimated_total_area_m2': int(total_area),
            'estimated_total_area_acres': round(total_area / 4047, 1),
            'estimated_images': total_images,
            'estimated_flight_time_min': round(total_time, 1),
            'estimated_batteries': batteries_needed,
            'number_of_flights': batteries_needed,
            'gsd_cm_pixel': round(planner.calculate_gsd(), 2),
            'coverage_per_image_m2': round(area_per_image, 1),
            'storage_required_gb': round(total_images * 5 / 1024, 1)  # ~5MB per image
        }

        return stats

    def print_mission_summary(self):
        """Print comprehensive mission summary"""
        stats = self.estimate_mission_stats()

        print("\n" + "="*60)
        print("🗺️  DRONE MAPPING MISSION SUMMARY")
        print("="*60)
        print(f"\nMission: {self.mission_name}")
        print(f"Drone: {stats['drone_name']}")
        print(f"Type: {self.config.get('mission_type', 'area_mapping').replace('_', ' ').title()}")
        print(f"\n📊 ESTIMATED MISSION STATISTICS:")
        print(f"  • Total Area: {stats['estimated_total_area_acres']} acres ({stats['estimated_total_area_m2']:,} m²)")
        print(f"  • Photos Required: ~{stats['estimated_images']:,}")
        print(f"  • Flight Time: ~{stats['estimated_flight_time_min']} minutes")
        print(f"  • Batteries Needed: {stats['estimated_batteries']}")
        print(f"  • Number of Flights: {stats['number_of_flights']}")
        print(f"  • Ground Resolution: {stats['gsd_cm_pixel']} cm/pixel")
        print(f"  • Storage Required: ~{stats['storage_required_gb']} GB")

        print(f"\n⏱️  TIME BREAKDOWN:")
        flight_days = stats['number_of_flights']
        processing_time = stats['estimated_images'] * 0.5 / 60  # 0.5 sec per image
        print(f"  • Data Capture: {flight_days} flight session(s)")
        print(f"  • Image Processing: ~{processing_time:.1f} hours")
        print(f"  • Total Project Time: {flight_days + 1} days")

        print(f"\n💰 RESOURCE REQUIREMENTS:")
        print(f"  • Drone Batteries: {stats['estimated_batteries']} fully charged")
        print(f"  • Storage Cards: {max(1, int(stats['storage_required_gb'] / 32))} x 32GB cards")
        print(f"  • Processing Power: 16GB+ RAM recommended")

    def create_execution_checklist(self):
        """Create detailed execution checklist"""
        checklist = f"""
DRONE MAPPING EXECUTION CHECKLIST
==================================

PHASE 1: PREPARATION (Day Before)
----------------------------------
□ Review flight plan and waypoints
□ Charge all batteries (minimum {self.estimate_mission_stats()['estimated_batteries']})
□ Format SD cards (need {self.estimate_mission_stats()['storage_required_gb']}GB space)
□ Check weather forecast
□ Notify neighbors about drone operations
□ Test drone and camera functionality
□ Update drone firmware if needed
□ Review emergency procedures

PHASE 2: FLIGHT DAY
-------------------
Morning (Before Flight):
□ Final weather check
□ Run preflight checklist script
□ Set up landing area with pad/markers
□ Brief any assistants/spotters

During Flight:
□ Complete pre-arm checks
□ Set home point
□ Start flight logging
□ Execute waypoint mission
□ Monitor battery levels (land at 30%)
□ Log any issues or deviations
□ Swap batteries between flights
□ Backup images after each flight

After Flight:
□ Download all images
□ Verify image count and GPS data
□ Backup to external drive
□ Clean drone and equipment
□ Note any maintenance needs

PHASE 3: PROCESSING
-------------------
□ Organize images by flight
□ Run image quality checks
□ Remove blurry/unusable images
□ Start processing pipeline
□ Generate orthomosaic
□ Create coverage report
□ Export final deliverables

PHASE 4: QUALITY CONTROL
------------------------
□ Review orthomosaic for gaps
□ Check edge matching
□ Verify georeferencing accuracy
□ Document any issues
□ Plan re-flights if needed

PHASE 5: DELIVERY
-----------------
□ Export in requested formats
□ Generate metadata files
□ Create project documentation
□ Package deliverables
□ Archive raw data
"""
        checklist_file = self.mission_dir / "execution_checklist.txt"
        with open(checklist_file, 'w') as f:
            f.write(checklist)

        print(f"\n📝 Execution checklist saved to: {checklist_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Mission Control for Drone Mapping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create new mission with DJI Mini 3 Pro for 50 acre area
  python mission_control.py --mission MyFarm --drone dji_mini_3_pro --area-acres 50

  # Create default mission and view summary
  python mission_control.py --mission TestArea

  # Generate flight plan
  python mission_control.py --mission TestArea --action plan --lat 40.7128 --lon -74.0060

  # Process images with OpenDroneMap
  python mission_control.py --mission TestArea --action process --use-odm
        """
    )
    parser.add_argument("--mission", type=str, help="Mission name")
    parser.add_argument("--drone", type=str, default=None,
                       help="Drone profile to use (see flight_planner.py --list-drones)")
    parser.add_argument("--area-acres", type=float, help="Estimated mapping area in acres")
    parser.add_argument("--area-m2", type=int, help="Estimated mapping area in square meters")
    parser.add_argument("--lat", type=float, help="Center latitude")
    parser.add_argument("--lon", type=float, help="Center longitude")
    parser.add_argument("--action", choices=['plan', 'preflight', 'process', 'summary', 'monitor'],
                       help="Action to perform")
    parser.add_argument("--use-odm", action="store_true",
                       help="Use OpenDroneMap for processing (requires Docker)")

    args = parser.parse_args()

    # Convert area if provided in acres
    area_m2 = args.area_m2
    if args.area_acres:
        area_m2 = int(args.area_acres * 4047)

    # Initialize mission control
    control = MissionControl(args.mission, drone_profile=args.drone, area_m2=area_m2)

    if args.action == 'summary' or not args.action:
        control.print_mission_summary()
        control.create_execution_checklist()

    elif args.action == 'preflight':
        if args.lat and args.lon:
            control.run_preflight_checks(args.lat, args.lon)
        else:
            print("Error: Latitude and longitude required for preflight checks")

    elif args.action == 'plan':
        if args.lat and args.lon:
            control.generate_flight_plan(args.lat, args.lon)
        else:
            print("Error: Latitude and longitude required for flight planning")

    elif args.action == 'process':
        control.process_images(use_odm=args.use_odm)

    elif args.action == 'monitor':
        control.monitor_odm_processing()

    print("\n" + "="*60)
    print("🎯 Mission Control Ready")
    print(f"   Mission Directory: {control.mission_dir}")
    print("="*60)

if __name__ == "__main__":
    main()