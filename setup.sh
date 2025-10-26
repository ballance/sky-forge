#!/bin/bash

echo "================================================"
echo "Drone Mapping System Setup"
echo "For Potensic Atom 2 - Neighborhood Mapping"
echo "================================================"

# Check Python version
echo -e "\n📦 Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✓ Python $PYTHON_VERSION found"
else
    echo "❌ Python 3 not found. Please install Python 3.8 or higher"
    exit 1
fi

# Create virtual environment
echo -e "\n📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo -e "\n📦 Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo -e "\n📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Python dependencies installed"

# Check for optional tools
echo -e "\n📦 Checking optional tools..."

# Check ImageMagick
if command -v convert &> /dev/null; then
    echo "✓ ImageMagick found (for simple mosaics)"
else
    echo "⚠ ImageMagick not found (optional - for simple mosaics)"
    echo "  Install with: brew install imagemagick (macOS) or apt-get install imagemagick (Linux)"
fi

# Check OpenDroneMap
if command -v odm &> /dev/null; then
    echo "✓ OpenDroneMap found (for professional processing)"
else
    echo "⚠ OpenDroneMap not found (optional - for professional orthomosaics)"
    echo "  Install instructions: https://www.opendronemap.org/odm/"
fi

# Check git
if command -v git &> /dev/null; then
    echo "✓ Git found"
else
    echo "⚠ Git not found (optional - for version control)"
fi

# Create mission directories
echo -e "\n📁 Creating directory structure..."
mkdir -p missions
mkdir -p templates
mkdir -p documentation
echo "✓ Directory structure created"

# Make scripts executable
echo -e "\n🔧 Setting up permissions..."
chmod +x *.py
chmod +x *.sh
echo "✓ Scripts made executable"

# Create initial mission
echo -e "\n🚁 Creating example mission..."
python3 -c "
from mission_control import MissionControl
control = MissionControl('example_mission')
control.create_execution_checklist()
print('✓ Example mission created: missions/example_mission')
"

echo -e "\n================================================"
echo "✅ SETUP COMPLETE!"
echo "================================================"
echo ""
echo "🚁 QUICK START:"
echo ""
echo "1. Activate the environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Run mission control summary:"
echo "   python mission_control.py --summary"
echo ""
echo "3. Generate a flight plan (replace with your coordinates):"
echo "   python flight_planner.py --center-lat 40.7128 --center-lon -74.0060 --area-size 400"
echo ""
echo "4. Run preflight checks:"
echo "   python preflight_checklist.py --lat 40.7128 --lon -74.0060"
echo ""
echo "5. Process captured images:"
echo "   python image_processor.py ./captured_images --output ./output"
echo ""
echo "📚 For detailed instructions, see README.md"
echo "================================================"