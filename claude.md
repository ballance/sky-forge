# Drone Mapping Utility Suite

A comprehensive Python-based toolkit for planning, executing, and processing drone mapping missions. This project provides end-to-end workflow automation for creating professional orthomosaics, 3D models, and terrain models from aerial imagery.

## Overview

This toolkit is designed for mapping areas of any size (from small properties to 100+ acre sites) using consumer drones. It supports multiple drone platforms including DJI, Autel, Potensic, and custom configurations. The system integrates flight planning, preflight safety checks, and professional photogrammetry processing using OpenDroneMap.

### Key Features

- **Mission Planning**: Automated flight path generation with optimal coverage
- **Preflight Checks**: Comprehensive safety validation (weather, airspace, regulations)
- **Image Processing**: Professional photogrammetry pipeline via OpenDroneMap
- **GPS Integration**: Automatic geotagging and georeferencing
- **Progress Tracking**: Mission organization with detailed reporting

## Project Structure

```
drone-util/
├── mission_control.py       # Central command interface
├── flight_planner.py         # Flight path generation
├── preflight_checklist.py    # Safety validation system
├── image_processor.py        # Photogrammetry pipeline
├── drone_profiles.json       # Drone specifications database
├── missions/                 # Mission data directory
│   └── [MissionName]/
│       ├── flight_plans/     # Generated flight paths
│       ├── captured_images/  # Drone photos (gitignored)
│       ├── outputs/          # Processing results (gitignored)
│       ├── logs/             # Mission logs
│       └── mission_config.json
├── .gitignore
├── README.md                 # Quick start guide
└── CLAUDE.md                 # This file (detailed documentation)
```

## System Architecture

### 1. Mission Control (`mission_control.py`)

Central orchestrator that manages the entire workflow.

**Key Functions:**
- Mission initialization and directory management
- Configuration management
- Workflow coordination
- Statistics estimation

**Usage:**
```bash
# View mission summary and estimates (uses default 40 acre area)
python mission_control.py --mission YourMissionName

# Create mission with specific drone and area size
python mission_control.py --mission MyFarm --drone dji_mini_3_pro --area-acres 50

# Run preflight checks
python mission_control.py --mission YourMissionName --action preflight --lat 40.7128 --lon -74.0060

# Generate flight plan
python mission_control.py --mission YourMissionName --action plan --lat 40.7128 --lon -74.0060

# Process captured images (simple mosaic)
python mission_control.py --mission YourMissionName --action process

# Process with OpenDroneMap (professional quality)
python mission_control.py --mission YourMissionName --action process --use-odm
```

### 2. Flight Planner (`flight_planner.py`)

Generates optimal flight paths with proper overlap and coverage.

**Features:**
- Grid-based lawn mower pattern
- Configurable overlap (forward/side)
- Altitude optimization for GSD targets
- GPS waypoint generation
- Multiple export formats (JSON, KML, Litchi CSV)

**Supported Drones:**
- Potensic Atom 2
- DJI Mini 3 Pro
- DJI Air 3
- DJI Mavic 3
- Autel EVO Lite+
- Custom (user-defined specifications)

**Configuration:**
All drone specifications are stored in `drone_profiles.json`. Each profile includes:
- Camera sensor dimensions and resolution
- Flight capabilities (speed, endurance, altitude)
- GPS and gimbal features

```bash
# List available drone profiles
python flight_planner.py --list-drones

# Generate plan with specific drone
python flight_planner.py --drone dji_mini_3_pro --center-lat 40.7128 --center-lon -74.0060
```

**Default Mapping Parameters:**
- Altitude: 70m (configurable)
- Forward overlap: 70%
- Side overlap: 60%
- Target GSD: ~2.0 cm/pixel (varies by drone)
```

### 3. Preflight Checklist (`preflight_checklist.py`)

Comprehensive safety validation before flight operations.

**Checks Performed:**
- Weather conditions (wind, visibility, precipitation)
- Airspace restrictions (controlled airspace, airports, NFZs)
- Legal compliance (FAA Part 107, registration)
- Flight time windows (daylight hours, civil twilight)
- Equipment readiness

**Integration:**
- OpenWeatherMap API for weather data
- FAA UAS Facility Maps for airspace
- Automated sunrise/sunset calculations

### 4. Image Processor (`image_processor.py`)

Professional photogrammetry pipeline with multiple processing modes.

**Processing Modes:**

**A. Simple Mosaic (Quick Preview)**
- Uses ImageMagick for basic stitching
- Fast processing (minutes)
- No georeferencing
- Good for quick visualization

**B. OpenDroneMap (Professional Quality)**
- Full photogrammetry pipeline
- Structure-from-Motion (SfM)
- Dense point cloud generation
- 3D mesh reconstruction
- Georeferenced orthomosaic
- Digital Surface Model (DSM)
- Digital Terrain Model (DTM)
- Processing time: 1-3 hours for 300+ images

**Features:**
- Automatic EXIF GPS extraction
- GPS coverage visualization (HTML map)
- Processing reports (JSON)
- Configurable quality settings

## Dependencies

### Required

**Python Packages:**
```bash
pip install exifread piexif
```

**System Tools:**
- Docker (for OpenDroneMap)
- ImageMagick 7+ (for simple mosaics)

**OpenDroneMap:**
```bash
docker pull opendronemap/odm
```

### Optional APIs

- **OpenWeatherMap**: Weather data for preflight checks
- **FAA UAS API**: Airspace validation

## Installation & Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd drone-util
```

### 2. Install Python Dependencies
```bash
pip install exifread piexif
```

### 3. Install System Dependencies

**macOS:**
```bash
brew install imagemagick
brew install --cask docker
```

**Linux:**
```bash
apt-get install imagemagick docker.io
```

### 4. Setup OpenDroneMap
```bash
docker pull opendronemap/odm
```

### 5. Configure APIs (Optional)
Create `.env` file:
```bash
OPENWEATHER_API_KEY=your_key_here
FAA_API_KEY=your_key_here
```

## Usage Examples

### Example 1: Complete Mission Workflow

```bash
# 1. Create new mission for 75-acre farm with DJI Air 3
python mission_control.py --mission FarmSurvey2025 --drone dji_air_3 --area-acres 75

# 2. Run preflight checks
python mission_control.py --mission FarmSurvey2025 \
  --action preflight \
  --lat 40.7128 \
  --lon -74.0060

# 3. Generate flight plan
python mission_control.py --mission FarmSurvey2025 \
  --action plan \
  --lat 40.7128 \
  --lon -74.0060

# 4. Fly the mission (manual - upload waypoints to drone)
# Copy images to missions/FarmSurvey2025/captured_images/

# 5. Process images with OpenDroneMap
python mission_control.py --mission FarmSurvey2025 \
  --action process \
  --use-odm
```

### Example 2: Quick Preview Processing

```bash
# Process with simple mosaic for quick results
python mission_control.py --mission TestFlight --action process

# View outputs
open missions/TestFlight/outputs/orthomosaic/simple_mosaic.jpg
open missions/TestFlight/outputs/reports/coverage_map.html
```

### Example 3: Custom Flight Planning

```python
from flight_planner import DroneSpecs, MappingParams, FlightPlanner

# Custom drone configuration
drone = DroneSpecs(
    max_flight_time=25,
    cruise_speed=10
)

# Custom mapping parameters
params = MappingParams(
    altitude=50,
    forward_overlap=80,
    side_overlap=70
)

# Generate plan
planner = FlightPlanner(drone, params)
waypoints = planner.generate_grid_pattern(
    center_lat=40.7128,
    center_lon=-74.0060,
    area_width=300,
    area_height=300
)

# Export
planner.export_to_litchi_csv(waypoints, "custom_plan.csv")
```

## OpenDroneMap Processing Details

### Processing Pipeline

1. **Dataset Loading** - Validates images and extracts metadata
2. **Feature Detection** - Extracts 10,000+ keypoints per image
3. **Feature Matching** - Finds correspondences between images
4. **Bundle Adjustment** - Camera pose optimization
5. **Dense Point Cloud** - Multi-view stereo reconstruction
6. **Mesh Generation** - 3D surface reconstruction
7. **Texturing** - Projects images onto 3D mesh
8. **Orthophoto** - Generates top-down georeferenced map
9. **DSM/DTM** - Elevation models with/without objects

### Output Files

After ODM processing completes, outputs are in:
```
missions/[MissionName]/outputs/odm_project/mapping_*/
├── odm_orthophoto/
│   └── odm_orthophoto.tif      # Georeferenced orthomosaic
├── odm_dem/
│   ├── dsm.tif                  # Digital Surface Model
│   └── dtm.tif                  # Digital Terrain Model
├── odm_texturing/
│   ├── odm_textured_model.obj   # 3D model
│   └── odm_textured_model.mtl
├── entwine_pointcloud/
│   └── ept.json                 # Point cloud (EPT format)
└── odm_report/
    └── report.pdf               # Processing report
```

### Quality Settings

**For Maximum Quality:**
```python
options = {
    'min-num-features': 20000,
    'feature-quality': 'ultra',
    'pc-quality': 'ultra',
    'orthophoto-resolution': 2.5
}
```

**For Faster Processing:**
```python
options = {
    'min-num-features': 8000,
    'feature-quality': 'medium',
    'pc-quality': 'medium',
    'orthophoto-resolution': 10,
    'fast-orthophoto': True
}
```

## Monitoring Active Processing

### Check ODM Progress
```bash
# Find running container
docker ps | grep opendronemap

# View live logs
docker logs -f <container_id>

# Or use container name
docker logs -f <container_name>
```

### Processing Status Indicators
- **"detect_features"** - Feature extraction (20-40% of time)
- **"match_features"** - Matching images (10-20%)
- **"reconstruction"** - Bundle adjustment (5-10%)
- **"opensfm"** to **"openmvs"** - Dense reconstruction (30-50%)
- **"odm_orthophoto"** - Final orthomosaic (5-10%)

## Performance Optimization

### For Large Datasets (500+ images)

**Split Processing:**
```python
options = {
    'split': 100,  # Process in groups of 100
    'split-overlap': 150  # 150px overlap between groups
}
```

**Resource Management:**
```python
options = {
    'max-concurrency': 4,  # Limit parallel processes
    'optimize-disk-space': True  # Remove intermediate files
}
```

### Hardware Recommendations

**Minimum:**
- 16GB RAM
- Quad-core CPU
- 50GB free disk space

**Recommended:**
- 32GB+ RAM
- 8+ core CPU
- 100GB+ SSD storage
- NVIDIA GPU (for GPU acceleration)

## Troubleshooting

### Common Issues

**1. ODM fails with "insufficient features"**
```bash
# Increase feature detection
--min-num-features 15000 --feature-quality ultra
```

**2. Out of memory errors**
```bash
# Enable split processing
--split 50 --max-concurrency 2
```

**3. Poor image alignment**
```bash
# Increase overlap in flight planning
forward_overlap=80, side_overlap=70
```

**4. Missing GPS data**
```bash
# Verify EXIF data
exiftool captured_images/IMG_001.JPG | grep GPS
```

### Debug Mode

Enable verbose logging:
```bash
docker run -it opendronemap/odm --verbose <options>
```

## Mission Configuration

Each mission has a `mission_config.json`:

```json
{
  "mission_name": "FarmSurvey2025",
  "mission_type": "area_mapping",
  "estimated_area_m2": 303525,
  "estimated_area_acres": 75.0,
  "drone_profile": "dji_air_3",
  "mapping_parameters": {
    "altitude_m": 70,
    "forward_overlap": 70,
    "side_overlap": 60,
    "gsd_target_cm": 2.0
  },
  "safety_parameters": {
    "max_wind_speed_ms": 10,
    "min_battery_percent": 30,
    "max_flight_time_min": 25
  },
  "processing_options": {
    "generate_orthomosaic": true,
    "generate_3d_model": false,
    "generate_dsm": true,
    "output_format": "GeoTIFF"
  }
}
```

## Adding Custom Drone Profiles

To add your own drone, edit `drone_profiles.json`:

```json
{
  "profiles": {
    "my_custom_drone": {
      "name": "My Custom Drone",
      "camera": {
        "sensor_width_mm": 13.2,
        "sensor_height_mm": 8.8,
        "focal_length_mm": 24,
        "image_width_px": 5472,
        "image_height_px": 3648,
        "resolution_mp": 20,
        "video_resolution": "4K"
      },
      "flight": {
        "max_flight_time_min": 30,
        "cruise_speed_ms": 10.0,
        "max_speed_ms": 18.0,
        "max_altitude_m": 120,
        "hover_accuracy_m": 0.3
      },
      "features": {
        "gps": true,
        "return_to_home": true,
        "gimbal_axes": 3,
        "obstacle_avoidance": true
      }
    }
  }
}
```

Then use it: `--drone my_custom_drone`

## Best Practices

### Flight Planning
- Survey area in daylight with good visibility
- Plan for 20% battery reserve
- Check weather forecast 24 hours ahead
- Maintain visual line of sight
- Have spotter for large areas

### Image Capture
- Use manual exposure settings
- Shoot in RAW if possible
- Minimize motion blur (fast shutter)
- Ensure 70%+ overlap
- Capture oblique images for 3D models

### Processing
- Start with simple mosaic for quick validation
- Use ODM for final deliverables
- Archive raw images before processing
- Save intermediate results
- Document any processing issues

## Safety & Legal Compliance

### Pre-flight Requirements
- FAA Part 107 certification (commercial use)
- Drone registration with FAA
- Airspace authorization if required
- Weather minimums (3 miles visibility, 500ft cloud ceiling)
- Daylight operations only (civil twilight with anti-collision lights)

### Operational Limits
- Maximum altitude: 400ft AGL
- Visual line of sight required
- No flying over people
- Respect privacy and property rights
- Emergency procedures documented

## Contributing

### Code Style
- Follow PEP 8 for Python code
- Document functions with docstrings
- Include type hints where appropriate
- Add comments for complex logic

### Testing
- Test flight plans in simulator first
- Validate GPS coordinates before flight
- Process sample datasets before full missions

## Resources

### Documentation
- [OpenDroneMap Docs](https://docs.opendronemap.org/)
- [FAA Part 107](https://www.faa.gov/uas/commercial_operators/become_a_drone_pilot)
- [B4UFLY App](https://www.faa.gov/uas/getting_started/b4ufly)

### APIs
- [OpenWeatherMap](https://openweathermap.org/api)
- [FAA UAS Facility Maps](https://faa.maps.arcgis.com/)

### Community
- [OpenDroneMap Community Forum](https://community.opendronemap.org/)
- [Drone Pilots Forum](https://www.dronepilotsforum.com/)

## License

[Add your license here]

## Acknowledgments

- OpenDroneMap team for the amazing photogrammetry tools
- Consumer drone manufacturers (DJI, Autel, Potensic, etc.) for making aerial mapping accessible
- FAA for comprehensive safety guidelines
- Open source community for tools and inspiration

---

**Last Updated:** October 2025
**Version:** 1.0
**Maintained by:** Claude AI Assistant & User
