# Drone Mapping Utility Suite

Professional drone mapping toolkit for creating orthomosaics, 3D models, and terrain maps from aerial imagery.

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone git@github.com:ballance/sky-forge.git
cd sky-forge

# Install Python dependencies
pip install exifread piexif

# Install system dependencies (macOS)
brew install imagemagick
brew install --cask docker

# Or on Linux
apt-get install imagemagick docker.io

# Pull OpenDroneMap (for professional processing)
docker pull opendronemap/odm
```

### 2. Choose Your Drone

List available drone profiles:

```bash
python flight_planner.py --list-drones
```

**Supported Drones:**
- `potensic_atom_2` - Potensic Atom 2 (12MP, 32min flight)
- `dji_mini_3_pro` - DJI Mini 3 Pro (12MP, 34min flight)
- `dji_air_3` - DJI Air 3 (48MP, 46min flight)
- `dji_mavic_3` - DJI Mavic 3 (20MP, 46min flight)
- `autel_evo_lite` - Autel EVO Lite+ (20MP, 40min flight)
- `custom` - Define your own specifications

### 3. Create a Mission

```bash
# Basic mission (uses default 40 acre area)
python mission_control.py --mission MyMission

# Specify drone and area
python mission_control.py --mission FarmSurvey \
  --drone dji_mini_3_pro \
  --area-acres 75

# Or use square meters
python mission_control.py --mission PropertyMap \
  --drone potensic_atom_2 \
  --area-m2 50000
```

This creates:
```
missions/YourMissionName/
├── flight_plans/       # Flight plans will go here
├── captured_images/    # Put your drone photos here
├── outputs/           # Processed maps appear here
├── logs/             # Mission logs
└── mission_config.json
```

### 4. Plan Your Flight

```bash
python mission_control.py --mission FarmSurvey \
  --action plan \
  --lat 40.7128 \
  --lon -74.0060
```

Output: `missions/FarmSurvey/flight_plans/flight_plan_*.json`

### 5. Run Preflight Checks

```bash
python mission_control.py --mission FarmSurvey \
  --action preflight \
  --lat 40.7128 \
  --lon -74.0060
```

Checks:
- Weather conditions (wind, visibility, precipitation)
- Airspace restrictions
- Legal compliance
- Flight time windows

### 6. Fly the Mission

1. Load waypoints from flight plan into your drone's app (Litchi, DJI Pilot, etc.)
2. Complete pre-flight checks
3. Execute autonomous mission
4. Copy captured images to `missions/YourMission/captured_images/`

### 7. Process Images

**Quick Preview (2-5 minutes):**
```bash
python mission_control.py --mission FarmSurvey --action process
```

**Professional Quality (1-3 hours):**
```bash
python mission_control.py --mission FarmSurvey --action process --use-odm
```

Outputs:
- `outputs/orthomosaic/` - Georeferenced map
- `outputs/odm_dem/` - Elevation models (DSM/DTM)
- `outputs/odm_texturing/` - 3D model
- `outputs/reports/` - Coverage maps and statistics

## Common Use Cases

### Small Property (< 10 acres)

```bash
python mission_control.py --mission BackyardSurvey \
  --drone dji_mini_3_pro \
  --area-acres 5

python mission_control.py --mission BackyardSurvey \
  --action plan \
  --lat 40.7128 \
  --lon -74.0060

# Fly mission, then process
python mission_control.py --mission BackyardSurvey \
  --action process --use-odm
```

### Large Farm (50-100 acres)

```bash
python mission_control.py --mission CornField2025 \
  --drone dji_air_3 \
  --area-acres 85

# Plan with custom altitude for better coverage
python flight_planner.py \
  --drone dji_air_3 \
  --center-lat 40.7128 \
  --center-lon -74.0060 \
  --area-size 600 \
  --altitude 100 \
  --output missions/CornField2025/flight_plans/custom_plan.json
```

### Construction Site Monitoring

```bash
python mission_control.py --mission SiteWeek12 \
  --drone dji_mavic_3 \
  --area-m2 40000

# Process for 3D model
# Edit mission_config.json: "generate_3d_model": true
python mission_control.py --mission SiteWeek12 \
  --action process --use-odm
```

## Adding Your Custom Drone

Edit `drone_profiles.json`:

```json
{
  "profiles": {
    "my_drone": {
      "name": "My Custom Drone",
      "camera": {
        "sensor_width_mm": 6.17,
        "sensor_height_mm": 4.63,
        "focal_length_mm": 4.5,
        "image_width_px": 4000,
        "image_height_px": 3000,
        "resolution_mp": 12,
        "video_resolution": "4K"
      },
      "flight": {
        "max_flight_time_min": 30,
        "cruise_speed_ms": 10.0,
        "max_speed_ms": 16.0,
        "max_altitude_m": 120,
        "hover_accuracy_m": 0.5
      },
      "features": {
        "gps": true,
        "return_to_home": true,
        "gimbal_axes": 3,
        "obstacle_avoidance": false
      }
    }
  }
}
```

Then use: `--drone my_drone`

## Customizing Mission Parameters

Edit `missions/YourMission/mission_config.json`:

```json
{
  "mapping_parameters": {
    "altitude_m": 70,           // Flight altitude
    "forward_overlap": 70,      // Image overlap (forward)
    "side_overlap": 60,         // Image overlap (side)
    "gsd_target_cm": 2.0        // Ground sample distance
  },
  "safety_parameters": {
    "max_wind_speed_ms": 10,    // Max wind for flight
    "min_battery_percent": 30,  // Battery reserve
    "max_flight_time_min": 25   // Max single flight
  },
  "processing_options": {
    "generate_orthomosaic": true,  // 2D map
    "generate_3d_model": false,    // 3D mesh
    "generate_dsm": true,          // Elevation model
    "output_format": "GeoTIFF"     // Output format
  }
}
```

## Monitoring Processing

Check OpenDroneMap progress:

```bash
# Find running container
docker ps | grep opendronemap

# View live logs
docker logs -f <container_name>
```

Processing stages:
1. **detect_features** (20-40% of time)
2. **match_features** (10-20%)
3. **reconstruction** (5-10%)
4. **dense reconstruction** (30-50%)
5. **orthophoto generation** (5-10%)

## Troubleshooting

**"No images found"**
- Place images in `missions/YourMission/captured_images/`
- Verify image format (JPG, JPEG, PNG supported)

**"Insufficient features detected"**
- Ensure 70%+ image overlap
- Check image quality (not blurry)
- Verify GPS data in EXIF: `exiftool image.jpg | grep GPS`

**"Out of memory"**
- Enable split processing in mission config
- Reduce image resolution or count
- Add more RAM (16GB minimum, 32GB recommended)

**"Flight plan too long for battery"**
- Mission will auto-split into multiple flights
- Use drone with longer flight time
- Reduce altitude to cover more area per flight

## Command Reference

### Mission Control
```bash
python mission_control.py --mission NAME [OPTIONS]
  --drone PROFILE         # Drone profile name
  --area-acres FLOAT      # Area in acres
  --area-m2 INT          # Area in square meters
  --action ACTION        # plan, preflight, process, summary
  --lat FLOAT           # Center latitude
  --lon FLOAT           # Center longitude
  --use-odm             # Use OpenDroneMap processing
```

### Flight Planner
```bash
python flight_planner.py [OPTIONS]
  --list-drones         # Show available drones
  --drone PROFILE       # Drone profile name
  --center-lat FLOAT    # Center latitude
  --center-lon FLOAT    # Center longitude
  --area-size FLOAT     # Area size (meters, square)
  --altitude FLOAT      # Flight altitude (meters)
  --output FILE         # Output file path
```

## Safety & Legal

**Before Flying:**
- [ ] FAA Part 107 certification (commercial use in US)
- [ ] Drone registration with FAA
- [ ] Check airspace restrictions (B4UFLY app)
- [ ] Weather conditions acceptable
- [ ] Daylight operations only (civil twilight with lights)
- [ ] Visual line of sight maintained
- [ ] Maximum altitude 400ft AGL

**Resources:**
- [FAA Part 107](https://www.faa.gov/uas/commercial_operators/become_a_drone_pilot)
- [B4UFLY App](https://www.faa.gov/uas/getting_started/b4ufly)
- [OpenDroneMap Docs](https://docs.opendronemap.org/)

## Performance Tips

**For faster processing:**
- Use `--simple-mosaic` for quick previews
- Reduce image count (increase altitude, reduce overlap)
- Enable split processing for 500+ images

**For better quality:**
- Lower altitude = better resolution
- Higher overlap (80%+) = better 3D models
- Shoot in RAW format if possible
- Maintain consistent lighting (avoid midday sun)

## Need Help?

- **Documentation:** See [CLAUDE.md](CLAUDE.md) for detailed information
- **Issues:** Check troubleshooting section above
- **Custom Drones:** Edit `drone_profiles.json`
- **Advanced Config:** Edit mission `mission_config.json`

## License

MIT License

Copyright (c) 2025 Chris Ballance

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

**Quick Command Checklist:**

```bash
# 1. List drones
python flight_planner.py --list-drones

# 2. Create mission
python mission_control.py --mission NAME --drone PROFILE --area-acres N

# 3. Plan flight
python mission_control.py --mission NAME --action plan --lat LAT --lon LON

# 4. Preflight check
python mission_control.py --mission NAME --action preflight --lat LAT --lon LON

# 5. [Fly mission manually]

# 6. Process images
python mission_control.py --mission NAME --action process --use-odm
```
