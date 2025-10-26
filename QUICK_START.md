# Quick Start Guide - Neighborhood Drone Mapping

## Overview
This guide walks you through mapping your 96-house neighborhood with the Potensic Atom 2 drone.

## Initial Setup (One Time)

### 1. Install the System
```bash
# Make setup script executable
chmod +x setup.sh

# Run setup
./setup.sh

# Activate Python environment
source venv/bin/activate
```

### 2. Configure Your Mission
Edit the coordinates for your neighborhood center:
```bash
# Find your neighborhood on Google Maps
# Right-click to copy coordinates (lat, lon)
export NEIGHBORHOOD_LAT=40.7128  # Replace with your latitude
export NEIGHBORHOOD_LON=-74.0060 # Replace with your longitude
```

## Pre-Flight Planning (Day Before)

### 1. Generate Flight Plan
```bash
# Create optimized flight plan for your neighborhood
python flight_planner.py \
    --center-lat $NEIGHBORHOOD_LAT \
    --center-lon $NEIGHBORHOOD_LON \
    --area-size 400 \
    --altitude 70 \
    --output my_neighborhood_plan.json
```

This will show:
- Number of waypoints needed
- Estimated flight time
- Number of batteries required
- Expected number of photos

### 2. Review Mission Statistics
```bash
# Get detailed mission breakdown
python mission_control.py --summary --mission "my_neighborhood"
```

Expected output for 96 houses:
- **Area**: ~40 acres
- **Photos**: ~800-1000
- **Flight time**: 60-90 minutes total
- **Batteries**: 3-4 fully charged
- **Storage**: ~5GB

### 3. Prepare Equipment
Based on the mission statistics, prepare:
- [ ] Drone + Remote Controller
- [ ] 4 charged batteries
- [ ] 32GB+ SD card (formatted)
- [ ] Smartphone with Potensic app
- [ ] Landing pad
- [ ] First aid kit
- [ ] Notebook for logging

## Flight Day

### 1. Morning Checks (30 min before)
```bash
# Run comprehensive preflight checks
python preflight_checklist.py \
    --lat $NEIGHBORHOOD_LAT \
    --lon $NEIGHBORHOOD_LON
```

**STOP if you see:**
- ❌ Wind speed > 10 m/s
- ❌ Precipitation detected
- ❌ Airspace restrictions

### 2. Flight Execution

#### Flight 1 (Battery 1)
1. **Set up landing area** with markers
2. **Power on drone** and controller
3. **Open Potensic app** on phone
4. **Load waypoint mission** (if supported) or fly manually:
   - Altitude: 70m (230ft)
   - Speed: 5-8 m/s
   - Pattern: Lawn mower (back and forth)
   - Photo interval: Every 3-5 seconds

5. **Monitor constantly:**
   - Battery level (land at 30%)
   - GPS signal strength
   - Wind conditions
   - Visual line of sight

6. **Land and swap battery** when at 30%

#### Flight 2-4 (Batteries 2-4)
- Continue from last position
- Maintain same altitude and overlap
- Complete remaining waypoints

### 3. After Each Flight
1. Download images from SD card
2. Create backup immediately
3. Quick review for issues
4. Log any problems

## Image Processing

### 1. Organize Images
```bash
# Create mission folder and move images
mkdir -p missions/my_neighborhood/images
cp /path/to/sd/card/*.jpg missions/my_neighborhood/images/
```

### 2. Process Images

#### Option A: Simple Mosaic (Quick)
```bash
python image_processor.py \
    missions/my_neighborhood/images \
    --output missions/my_neighborhood/output \
    --simple-mosaic
```

#### Option B: Professional Orthomosaic (If ODM installed)
```bash
python image_processor.py \
    missions/my_neighborhood/images \
    --output missions/my_neighborhood/output \
    --use-odm
```

### 3. Review Results
- Open `output/reports/coverage_map.html` to see flight coverage
- Check `output/orthomosaic/` for final map
- Review `output/reports/report_*.json` for statistics

## Troubleshooting

### Common Issues and Solutions

#### "Not enough overlap between images"
- Fly slower (5 m/s max)
- Increase overlap to 80% front, 70% side
- Ensure consistent altitude

#### "GPS data missing from images"
- Wait for GPS lock before takeoff (10+ satellites)
- Check drone GPS settings in app
- Ensure GPS metadata is enabled

#### "Images are blurry"
- Check gimbal is stable
- Reduce flight speed
- Avoid flying in high winds
- Clean camera lens

#### "Battery depletes too fast"
- Reduce flight speed
- Lower altitude if possible
- Check battery health
- Avoid cold weather flying

#### "Can't process all images at once"
- Split into smaller batches
- Increase computer RAM/swap space
- Use cloud processing services

## Tips for Best Results

### Optimal Conditions
- **Time**: 10 AM - 2 PM (minimal shadows)
- **Weather**: Overcast (even lighting)
- **Wind**: < 5 m/s
- **Visibility**: > 5 km

### Flight Pattern Tips
1. **Snake pattern**: More efficient than separate lines
2. **Cross-hatch**: Fly perpendicular patterns for better 3D
3. **Overlap margins**: Add 10% extra overlap for safety
4. **Edge buffer**: Extend pattern 50m beyond target area

### Safety Reminders
- **Always** maintain visual line of sight
- **Never** fly over people or moving vehicles
- **Stop** immediately if aircraft approaches
- **Land** if you lose GPS or control signal
- **Check** battery voltage, not just percentage

## Complete Workflow Timeline

### Day 1: Planning (1 hour)
- Generate flight plans
- Check weather forecast
- Notify neighbors
- Charge batteries

### Day 2: Flying (2-3 hours)
- Morning: Preflight checks
- Execute 3-4 flights
- Download and backup images
- Quick quality check

### Day 3: Processing (2-4 hours)
- Organize images
- Run processing pipeline
- Generate orthomosaic
- Create final deliverables

### Total Project Time: ~3 days

## Next Steps

Once you've completed your first mapping:

1. **Analyze the results**
   - Check for coverage gaps
   - Identify areas needing re-flight
   - Note quality issues

2. **Optimize for next time**
   - Adjust altitude for better/worse resolution
   - Modify overlap based on results
   - Update flight speed settings

3. **Advanced features**
   - Add ground control points for accuracy
   - Create 3D models
   - Generate elevation models
   - Time-lapse mapping (seasonal changes)

## Support Resources

- **Potensic Atom 2 Manual**: Check drone documentation
- **FAA Resources**: www.faa.gov/uas
- **OpenDroneMap Forum**: community.opendronemap.org
- **Local Drone Groups**: Search Facebook/Meetup

---

Remember: **Safety First!** When in doubt, don't fly. It's better to wait for ideal conditions than risk your drone or others' safety.