#!/usr/bin/env python3
"""
Pre-flight Checklist and Safety System for Drone Mapping
Ensures safe and legal drone operations
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import argparse

class PreflightChecker:
    def __init__(self, location: Tuple[float, float]):
        self.latitude, self.longitude = location
        self.checks = []
        self.warnings = []
        self.errors = []

    def check_weather(self, api_key: str = None) -> Dict:
        """Check weather conditions for safe flying"""
        print("\n📋 Checking Weather Conditions...")

        if api_key:
            # Use OpenWeatherMap API if key provided
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': self.latitude,
                'lon': self.longitude,
                'appid': api_key,
                'units': 'metric'
            }

            try:
                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()

                    wind_speed = data['wind']['speed']  # m/s
                    visibility = data.get('visibility', 10000) / 1000  # km
                    weather_desc = data['weather'][0]['description']

                    weather_info = {
                        'wind_speed_ms': wind_speed,
                        'visibility_km': visibility,
                        'description': weather_desc,
                        'temperature': data['main']['temp'],
                        'clouds': data['clouds']['all']
                    }

                    # Check conditions
                    if wind_speed > 10:
                        self.errors.append(f"Wind speed too high: {wind_speed:.1f} m/s (max: 10 m/s)")
                    elif wind_speed > 8:
                        self.warnings.append(f"High wind speed: {wind_speed:.1f} m/s")
                    else:
                        self.checks.append(f"✓ Wind speed OK: {wind_speed:.1f} m/s")

                    if visibility < 3:
                        self.errors.append(f"Poor visibility: {visibility:.1f} km (min: 3 km)")
                    else:
                        self.checks.append(f"✓ Visibility OK: {visibility:.1f} km")

                    if 'rain' in weather_desc or 'snow' in weather_desc:
                        self.errors.append(f"Precipitation detected: {weather_desc}")
                    else:
                        self.checks.append(f"✓ No precipitation: {weather_desc}")

                    return weather_info
            except Exception as e:
                self.warnings.append(f"Could not fetch weather data: {e}")
        else:
            self.warnings.append("No weather API key provided - manual weather check required")

        return {}

    def check_airspace(self) -> Dict:
        """Check for airspace restrictions (simplified)"""
        print("\n📋 Checking Airspace Restrictions...")

        # This is a simplified check - in reality, you'd want to use
        # services like AirMap API or FAA B4UFLY

        airspace_info = {
            'class': 'G',  # Uncontrolled airspace
            'max_altitude_ft': 400,
            'restrictions': []
        }

        # Check for nearby airports (simplified radius check)
        # In production, use proper airspace data
        major_airports = [
            {'name': 'JFK', 'lat': 40.6413, 'lon': -73.7781, 'radius_nm': 5},
            {'name': 'LAX', 'lat': 33.9425, 'lon': -118.4081, 'radius_nm': 5},
            # Add more airports as needed
        ]

        for airport in major_airports:
            # Calculate distance (simplified)
            dist_deg = ((self.latitude - airport['lat'])**2 +
                       (self.longitude - airport['lon'])**2)**0.5
            dist_nm = dist_deg * 60  # Rough conversion

            if dist_nm < airport['radius_nm']:
                self.errors.append(f"Within {airport['name']} controlled airspace!")
                airspace_info['restrictions'].append(f"Airport: {airport['name']}")
            elif dist_nm < airport['radius_nm'] * 2:
                self.warnings.append(f"Near {airport['name']} airspace - check NOTAMS")

        if not airspace_info['restrictions']:
            self.checks.append("✓ No major airspace restrictions detected")

        return airspace_info

    def check_time_of_day(self) -> Dict:
        """Check if flying during appropriate hours"""
        print("\n📋 Checking Time Restrictions...")

        current_hour = datetime.now().hour
        time_info = {
            'current_hour': current_hour,
            'is_daylight': 6 <= current_hour <= 18,
            'optimal_lighting': 9 <= current_hour <= 16
        }

        if not time_info['is_daylight']:
            self.errors.append("Night operations require Part 107.29 waiver")
        elif not time_info['optimal_lighting']:
            self.warnings.append("Non-optimal lighting conditions for mapping")
        else:
            self.checks.append("✓ Good lighting conditions for mapping")

        return time_info

    def equipment_checklist(self) -> List[Dict]:
        """Generate equipment checklist"""
        checklist = [
            {'item': 'Drone (Potensic Atom 2)', 'required': True, 'checked': False},
            {'item': 'Remote Controller', 'required': True, 'checked': False},
            {'item': 'Charged Batteries (minimum 2)', 'required': True, 'checked': False},
            {'item': 'MicroSD Card (minimum 32GB)', 'required': True, 'checked': False},
            {'item': 'Smartphone with App', 'required': True, 'checked': False},
            {'item': 'Propeller Guards', 'required': False, 'checked': False},
            {'item': 'Landing Pad', 'required': False, 'checked': False},
            {'item': 'Sun Hood for Phone', 'required': False, 'checked': False},
            {'item': 'First Aid Kit', 'required': False, 'checked': False},
            {'item': 'Fire Extinguisher', 'required': False, 'checked': False},
            {'item': 'Visual Observer (if needed)', 'required': False, 'checked': False},
            {'item': 'High-Visibility Vest', 'required': False, 'checked': False},
        ]
        return checklist

    def regulatory_checklist(self) -> List[Dict]:
        """Generate regulatory compliance checklist"""
        checklist = [
            {'requirement': 'Part 107 Certificate (or recreational rules)', 'met': False},
            {'requirement': 'Drone Registration (FAA)', 'met': False},
            {'requirement': 'LAANC Authorization (if required)', 'met': False},
            {'requirement': 'Property Owner Permission', 'met': False},
            {'requirement': 'Neighbor Notifications', 'met': False},
            {'requirement': 'Insurance Coverage', 'met': False},
            {'requirement': 'Local Regulations Checked', 'met': False},
            {'requirement': 'NOTAMS Checked', 'met': False},
        ]
        return checklist

    def generate_report(self, save_to_file: bool = True) -> Dict:
        """Generate comprehensive preflight report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'location': {
                'latitude': self.latitude,
                'longitude': self.longitude
            },
            'checks_passed': self.checks,
            'warnings': self.warnings,
            'errors': self.errors,
            'equipment_checklist': self.equipment_checklist(),
            'regulatory_checklist': self.regulatory_checklist(),
            'go_no_go': len(self.errors) == 0
        }

        if save_to_file:
            filename = f"preflight_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {filename}")

        return report

    def print_summary(self):
        """Print preflight check summary"""
        print("\n" + "="*50)
        print("PREFLIGHT CHECK SUMMARY")
        print("="*50)

        if self.checks:
            print("\n✅ CHECKS PASSED:")
            for check in self.checks:
                print(f"  {check}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")

        if self.errors:
            print("\n❌ ERRORS (Must resolve before flight):")
            for error in self.errors:
                print(f"  {error}")

        print("\n" + "="*50)
        if len(self.errors) == 0:
            print("✅ GO FOR FLIGHT (Review warnings)")
        else:
            print("❌ NO GO - Resolve errors before flying")
        print("="*50)

class SafetyMonitor:
    """Real-time safety monitoring during flight"""

    def __init__(self, max_altitude_m: float = 120, max_distance_m: float = 500):
        self.max_altitude = max_altitude_m
        self.max_distance = max_distance_m
        self.home_position = None
        self.flight_start_time = None
        self.battery_warnings = []

    def set_home_position(self, lat: float, lon: float, alt: float = 0):
        """Set home position for return-to-home"""
        self.home_position = {'latitude': lat, 'longitude': lon, 'altitude': alt}
        self.flight_start_time = datetime.now()
        print(f"Home position set: {lat:.6f}, {lon:.6f}")

    def check_altitude(self, current_altitude: float) -> bool:
        """Check if altitude is within limits"""
        if current_altitude > self.max_altitude:
            print(f"⚠️  ALTITUDE WARNING: {current_altitude}m exceeds limit of {self.max_altitude}m")
            return False
        return True

    def check_distance(self, current_lat: float, current_lon: float) -> float:
        """Check distance from home position"""
        if not self.home_position:
            return 0

        # Simplified distance calculation
        R = 6371000  # Earth radius in meters
        lat1, lon1 = self.home_position['latitude'], self.home_position['longitude']

        dlat = current_lat - lat1
        dlon = current_lon - lon1

        # Approximate for small distances
        distance = R * ((dlat * 0.017453)**2 + (dlon * 0.017453)**2)**0.5

        if distance > self.max_distance:
            print(f"⚠️  DISTANCE WARNING: {distance:.0f}m from home (max: {self.max_distance}m)")

        return distance

    def check_battery(self, battery_percent: float, flight_time_minutes: float) -> str:
        """Monitor battery levels and estimate remaining flight time"""
        status = "OK"

        if battery_percent < 20:
            status = "CRITICAL - RTH NOW"
            print(f"🔴 BATTERY CRITICAL: {battery_percent}% - RETURN TO HOME IMMEDIATELY")
        elif battery_percent < 30:
            status = "LOW - RTH SOON"
            print(f"🟡 BATTERY LOW: {battery_percent}% - Initiate return to home")
        elif battery_percent < 50:
            status = "MONITOR"
            print(f"🟡 BATTERY: {battery_percent}% - Monitor closely")

        # Estimate remaining flight time
        if flight_time_minutes > 0:
            discharge_rate = (100 - battery_percent) / flight_time_minutes
            if discharge_rate > 0:
                remaining_minutes = battery_percent / discharge_rate
                print(f"  Estimated remaining flight time: {remaining_minutes:.1f} minutes")

        return status

def main():
    parser = argparse.ArgumentParser(description="Drone mapping preflight checker")
    parser.add_argument("--lat", type=float, required=True,
                       help="Latitude of flight area")
    parser.add_argument("--lon", type=float, required=True,
                       help="Longitude of flight area")
    parser.add_argument("--weather-api", type=str,
                       help="OpenWeatherMap API key for weather checks")
    parser.add_argument("--skip-weather", action="store_true",
                       help="Skip weather checks")

    args = parser.parse_args()

    # Run preflight checks
    checker = PreflightChecker((args.lat, args.lon))

    if not args.skip_weather:
        checker.check_weather(args.weather_api)

    checker.check_airspace()
    checker.check_time_of_day()

    # Generate and display report
    report = checker.generate_report()
    checker.print_summary()

    # Print checklists
    print("\n📋 EQUIPMENT CHECKLIST:")
    for item in report['equipment_checklist']:
        status = "[ ]" if not item['checked'] else "[✓]"
        required = "(Required)" if item['required'] else "(Optional)"
        print(f"  {status} {item['item']} {required}")

    print("\n📋 REGULATORY CHECKLIST:")
    for item in report['regulatory_checklist']:
        status = "[ ]" if not item['met'] else "[✓]"
        print(f"  {status} {item['requirement']}")

    print("\n💡 FLIGHT TIPS:")
    print("  • Maintain visual line of sight at all times")
    print("  • Fly at consistent speed (5-8 m/s) for best image quality")
    print("  • Monitor battery levels constantly")
    print("  • Have a spotter if flying near obstacles")
    print("  • Land immediately if any issues arise")

if __name__ == "__main__":
    main()