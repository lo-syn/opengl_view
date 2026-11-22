#!/bin/bash

# Test script to run the application with debug logging enabled
# This will help diagnose why Bluetooth audio isn't updating OSC controls

echo "=================================="
echo "Starting OpenGL Viewer with Debug Logging"
echo "=================================="
echo ""
echo "Instructions:"
echo "1. Wait for the OpenGL window and menu to appear"
echo "2. Navigate to SETTINGS and enable audio (cycle through modes)"
echo "3. Try File Audio first to establish baseline"
echo "4. Then try Bluetooth Audio"
echo ""
echo "Watch the logs below for:"
echo "  - 'Audio buffer received' - confirms buffers are being processed"
echo "  - 'Sending OSC message' - confirms OSC messages are being sent"
echo "  - 'Bluetooth mode active' - confirms Bluetooth mode is engaged"
echo ""
echo "Save this output to a file for analysis:"
echo "  ./run_app.sh 2>&1 | tee debug_logs_$(date +%Y%m%d_%H%M%S).txt"
echo ""
echo "=================================="
echo ""

# Configure Python logging to show DEBUG level messages
export PYTHONUNBUFFERED=1

# Run the shader menu application with logging
cd "$(dirname "$0")"

python3 shader_menu.py
