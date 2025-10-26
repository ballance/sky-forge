#!/usr/bin/env python3
"""
Mission Control Center for Neighborhood Drone Mapping
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
    def __init__(self, mission_name: str = None):
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

        self.config = self.load_or_create_config()

    def load_or_create_config(self) -> Dict:
        """Load or create mission configuration"""
        config_file = self.mission_dir / "mission_config.json"

        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)

        # Default configuration for 96-house neighborhood
        config = {
            'mission_name': self.mission_name,
            'target_houses': 96,
            'estimated_area_m2': 160000,  # ~40 acres for 96 houses
            'drone_model': 'Potensic Atom 2',
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
                           area_size: float = 400) -> str:
        """Generate optimized flight plan"""
        print("\n" + "="*60)
        print("📍 GENERATING FLIGHT PLAN")
        print("="*60)

        output_file = self.plans_dir / f"flight_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        cmd = [
            sys.executable,
            'flight_planner.py',
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
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            return "successfully" in result.stdout.lower()

        except Exception as e:
            print(f"Error processing images: {e}")
            return False

    def estimate_mission_stats(self) -> Dict:
        """Estimate mission statistics for 96-house neighborhood"""
        # Typical suburban neighborhood assumptions
        avg_lot_size = 1600  # m² (~0.4 acres)
        total_area = avg_lot_size * self.config['target_houses']

        # Including streets and common areas (add 30%)
        total_area_with_streets = total_area * 1.3

        # Calculate based on drone capabilities
        from flight_planner import DroneSpecs, MappingParams, FlightPlanner

        drone = DroneSpecs()
        params = MappingParams(altitude=self.config['mapping_parameters']['altitude_m'])
        planner = FlightPlanner(drone, params)

        # Calculate coverage
        image_width, image_height = planner.calculate_footprint()
        area_per_image = image_width * image_height

        forward_overlap = self.config['mapping_parameters']['forward_overlap'] / 100
        side_overlap = self.config['mapping_parameters']['side_overlap'] / 100
        effective_area_per_image = area_per_image * (1 - forward_overlap) * (1 - side_overlap)

        total_images = int(total_area_with_streets / effective_area_per_image * 1.2)  # 20% safety margin

        # Time estimation
        photo_time = total_images * 2  # 2 seconds per photo
        flight_distance = (total_area_with_streets ** 0.5) * 20  # Rough estimate
        flight_time = flight_distance / drone.cruise_speed
        total_time = (photo_time + flight_time) / 60  # Convert to minutes

        batteries_needed = int(total_time / (drone.max_flight_time * 0.8)) + 1

        stats = {
            'target_houses': self.config['target_houses'],
            'estimated_total_area_m2': int(total_area_with_streets),
            'estimated_total_area_acres': round(total_area_with_streets / 4047, 1),
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
        print("🏘️  NEIGHBORHOOD MAPPING MISSION SUMMARY")
        print("="*60)
        print(f"\nMission: {self.mission_name}")
        print(f"Target: {stats['target_houses']} houses")
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
    parser = argparse.ArgumentParser(description="Mission Control for Drone Mapping")
    parser.add_argument("--mission", type=str, help="Mission name")
    parser.add_argument("--lat", type=float, help="Center latitude")
    parser.add_argument("--lon", type=float, help="Center longitude")
    parser.add_argument("--action", choices=['plan', 'preflight', 'process', 'summary'],
                       help="Action to perform")
    parser.add_argument("--use-odm", action="store_true",
                       help="Use OpenDroneMap for processing (requires Docker)")

    args = parser.parse_args()

    # Initialize mission control
    control = MissionControl(args.mission)

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

    print("\n" + "="*60)
    print("🎯 Mission Control Ready")
    print(f"   Mission Directory: {control.mission_dir}")
    print("="*60)

if __name__ == "__main__":
    main()