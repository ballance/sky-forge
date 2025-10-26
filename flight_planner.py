#!/usr/bin/env python3
"""
Automated Flight Planning for Neighborhood Drone Mapping
Generates optimal flight paths for the Potensic Atom 2 drone
"""

import json
import math
import os
from dataclasses import dataclass
from typing import List, Tuple, Dict
import argparse
from datetime import datetime

@dataclass
class DroneSpecs:
    """Potensic Atom 2 specifications"""
    camera_sensor_width: float = 6.17  # mm (1/2.3" sensor)
    camera_sensor_height: float = 4.63  # mm
    focal_length: float = 4.5  # mm (approximate)
    image_width: int = 4000  # pixels (12MP photo mode)
    image_height: int = 3000  # pixels
    max_flight_time: int = 32  # minutes
    cruise_speed: float = 8.0  # m/s
    max_altitude: float = 120  # meters (FAA limit)

@dataclass
class MappingParams:
    """Parameters for mapping mission"""
    altitude: float = 70  # meters
    forward_overlap: float = 70  # percent
    side_overlap: float = 60  # percent
    gimbal_angle: float = -90  # degrees (straight down)

class FlightPlanner:
    def __init__(self, drone_specs: DroneSpecs, mapping_params: MappingParams):
        self.drone = drone_specs
        self.params = mapping_params

    def calculate_gsd(self) -> float:
        """Calculate Ground Sample Distance (cm/pixel)"""
        # GSD = (sensor_width * altitude * 100) / (focal_length * image_width)
        gsd = (self.drone.camera_sensor_width * self.params.altitude * 100) / \
               (self.drone.focal_length * self.drone.image_width)
        return gsd

    def calculate_footprint(self) -> Tuple[float, float]:
        """Calculate image footprint on ground (meters)"""
        gsd_meters = self.calculate_gsd() / 100
        width = self.drone.image_width * gsd_meters
        height = self.drone.image_height * gsd_meters
        return width, height

    def calculate_spacing(self) -> Tuple[float, float]:
        """Calculate spacing between photo positions"""
        width, height = self.calculate_footprint()

        # Calculate spacing based on overlap percentages
        forward_spacing = height * (1 - self.params.forward_overlap / 100)
        side_spacing = width * (1 - self.params.side_overlap / 100)

        return forward_spacing, side_spacing

    def generate_grid_pattern(self, boundary_coords: List[Tuple[float, float]]) -> List[Dict]:
        """
        Generate grid flight pattern for given boundary
        boundary_coords: List of (lat, lon) tuples defining area boundary
        """
        # Find bounding box
        lats = [coord[0] for coord in boundary_coords]
        lons = [coord[1] for coord in boundary_coords]

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        # Convert to meters (approximate for small areas)
        lat_to_meters = 111320.0  # meters per degree latitude
        lon_to_meters = lat_to_meters * math.cos(math.radians((min_lat + max_lat) / 2))

        area_width = (max_lon - min_lon) * lon_to_meters
        area_height = (max_lat - min_lat) * lat_to_meters

        forward_spacing, side_spacing = self.calculate_spacing()

        # Calculate number of flight lines
        num_lines = int(math.ceil(area_width / side_spacing)) + 1
        points_per_line = int(math.ceil(area_height / forward_spacing)) + 1

        waypoints = []
        line_direction = 1  # Alternate direction for efficiency

        for line_idx in range(num_lines):
            lon_offset = (line_idx * side_spacing) / lon_to_meters
            current_lon = min_lon + lon_offset

            if line_direction == 1:
                # Fly north
                for point_idx in range(points_per_line):
                    lat_offset = (point_idx * forward_spacing) / lat_to_meters
                    current_lat = min_lat + lat_offset

                    waypoint = {
                        "id": len(waypoints) + 1,
                        "latitude": current_lat,
                        "longitude": current_lon,
                        "altitude": self.params.altitude,
                        "gimbal_angle": self.params.gimbal_angle,
                        "action": "photo",
                        "line": line_idx + 1,
                        "point": point_idx + 1
                    }
                    waypoints.append(waypoint)
            else:
                # Fly south (reverse order for snake pattern)
                for point_idx in range(points_per_line - 1, -1, -1):
                    lat_offset = (point_idx * forward_spacing) / lat_to_meters
                    current_lat = min_lat + lat_offset

                    waypoint = {
                        "id": len(waypoints) + 1,
                        "latitude": current_lat,
                        "longitude": current_lon,
                        "altitude": self.params.altitude,
                        "gimbal_angle": self.params.gimbal_angle,
                        "action": "photo",
                        "line": line_idx + 1,
                        "point": point_idx + 1
                    }
                    waypoints.append(waypoint)

            line_direction *= -1  # Alternate direction

        return waypoints

    def estimate_mission_time(self, waypoints: List[Dict]) -> Dict:
        """Estimate total mission time and battery requirements"""
        if not waypoints:
            return {"error": "No waypoints provided"}

        total_distance = 0

        # Calculate distance between consecutive waypoints
        for i in range(1, len(waypoints)):
            lat1, lon1 = waypoints[i-1]["latitude"], waypoints[i-1]["longitude"]
            lat2, lon2 = waypoints[i]["latitude"], waypoints[i]["longitude"]

            # Haversine formula for distance
            R = 6371000  # Earth radius in meters
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lon2 - lon1)

            a = math.sin(delta_phi/2)**2 + \
                math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c
            total_distance += distance

        # Add takeoff and landing altitude
        total_distance += 2 * self.params.altitude

        # Calculate time
        flight_time = total_distance / self.drone.cruise_speed
        photo_time = len(waypoints) * 2  # 2 seconds per photo (conservative)
        total_time_seconds = flight_time + photo_time
        total_time_minutes = total_time_seconds / 60

        # Battery estimation
        batteries_needed = math.ceil(total_time_minutes / (self.drone.max_flight_time * 0.8))

        return {
            "total_waypoints": len(waypoints),
            "total_distance_m": round(total_distance, 2),
            "flight_time_min": round(flight_time / 60, 2),
            "photo_time_min": round(photo_time / 60, 2),
            "total_time_min": round(total_time_minutes, 2),
            "batteries_needed": batteries_needed,
            "estimated_photos": len(waypoints),
            "gsd_cm_per_pixel": round(self.calculate_gsd(), 2),
            "coverage_per_photo_m2": round(self.calculate_footprint()[0] *
                                          self.calculate_footprint()[1], 2)
        }

    def split_into_flights(self, waypoints: List[Dict],
                          battery_safety_margin: float = 0.8) -> List[List[Dict]]:
        """Split waypoints into multiple flights based on battery capacity"""
        max_flight_seconds = self.drone.max_flight_time * 60 * battery_safety_margin

        flights = []
        current_flight = []
        current_time = 0
        last_position = None

        for waypoint in waypoints:
            # Calculate time to reach this waypoint
            if last_position:
                lat1, lon1 = last_position["latitude"], last_position["longitude"]
                lat2, lon2 = waypoint["latitude"], waypoint["longitude"]

                # Calculate distance (simplified)
                R = 6371000
                phi1, phi2 = math.radians(lat1), math.radians(lat2)
                delta_phi = math.radians(lat2 - lat1)
                delta_lambda = math.radians(lon2 - lon1)

                a = math.sin(delta_phi/2)**2 + \
                    math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = R * c

                travel_time = distance / self.drone.cruise_speed
            else:
                travel_time = self.params.altitude / self.drone.cruise_speed  # Takeoff

            photo_time = 2  # seconds per photo
            segment_time = travel_time + photo_time

            # Check if adding this waypoint exceeds battery capacity
            if current_time + segment_time + (self.params.altitude / self.drone.cruise_speed) > max_flight_seconds:
                # Start new flight
                if current_flight:
                    flights.append(current_flight)
                current_flight = [waypoint]
                current_time = self.params.altitude / self.drone.cruise_speed + photo_time
            else:
                current_flight.append(waypoint)
                current_time += segment_time

            last_position = waypoint

        if current_flight:
            flights.append(current_flight)

        return flights

def main():
    parser = argparse.ArgumentParser(description="Generate flight plan for drone mapping")
    parser.add_argument("--area-size", type=float, default=500,
                       help="Approximate area size in meters (square)")
    parser.add_argument("--center-lat", type=float, default=40.7128,
                       help="Center latitude of mapping area")
    parser.add_argument("--center-lon", type=float, default=-74.0060,
                       help="Center longitude of mapping area")
    parser.add_argument("--altitude", type=float, default=70,
                       help="Flight altitude in meters")
    parser.add_argument("--output", type=str, default="flight_plan.json",
                       help="Output file for flight plan")

    args = parser.parse_args()

    # Initialize planner
    drone = DroneSpecs()
    params = MappingParams(altitude=args.altitude)
    planner = FlightPlanner(drone, params)

    # Generate boundary (square around center point)
    half_size = args.area_size / 2
    lat_offset = half_size / 111320.0
    lon_offset = half_size / (111320.0 * math.cos(math.radians(args.center_lat)))

    boundary = [
        (args.center_lat - lat_offset, args.center_lon - lon_offset),
        (args.center_lat - lat_offset, args.center_lon + lon_offset),
        (args.center_lat + lat_offset, args.center_lon + lon_offset),
        (args.center_lat + lat_offset, args.center_lon - lon_offset),
    ]

    # Generate waypoints
    waypoints = planner.generate_grid_pattern(boundary)

    # Estimate mission parameters
    mission_stats = planner.estimate_mission_time(waypoints)

    # Split into flights if needed
    flights = planner.split_into_flights(waypoints)

    # Prepare output
    output = {
        "mission_name": f"Neighborhood_Mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "drone": "Potensic Atom 2",
        "creation_date": datetime.now().isoformat(),
        "parameters": {
            "altitude_m": params.altitude,
            "forward_overlap_percent": params.forward_overlap,
            "side_overlap_percent": params.side_overlap,
            "gimbal_angle": params.gimbal_angle
        },
        "statistics": mission_stats,
        "boundary_coords": boundary,
        "total_flights": len(flights),
        "flights": [
            {
                "flight_number": i + 1,
                "waypoints": flight,
                "waypoint_count": len(flight)
            }
            for i, flight in enumerate(flights)
        ]
    }

    # Save to file
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\n=== Flight Plan Generated ===")
    print(f"Output saved to: {args.output}")
    print(f"\nMission Statistics:")
    print(f"  Total waypoints: {mission_stats['total_waypoints']}")
    print(f"  Total distance: {mission_stats['total_distance_m']:.0f} meters")
    print(f"  Estimated time: {mission_stats['total_time_min']:.1f} minutes")
    print(f"  Batteries needed: {mission_stats['batteries_needed']}")
    print(f"  Number of flights: {len(flights)}")
    print(f"  GSD: {mission_stats['gsd_cm_per_pixel']:.2f} cm/pixel")
    print(f"  Estimated photos: {mission_stats['estimated_photos']}")

    if len(flights) > 1:
        print(f"\nFlight breakdown:")
        for i, flight in enumerate(flights, 1):
            print(f"  Flight {i}: {len(flight)} waypoints")

if __name__ == "__main__":
    main()