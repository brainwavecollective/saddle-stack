###########################################
#
#  Brain Wave Collective
#  https://brainwavecollective.ai 
# 
#    Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench.
#	 Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
#
#  File: app.sh
#  Created: 2024
#  Authors: Thienthanh Trinh & Daniel Ritchie
#
#  Copyright (c) 2024 Brain Wave Collective
###########################################

#!/bin/bash

# Exit script if any command fails
set -e

# Get the absolute path to the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Needed by one of the containers, OK to leave blank because we're sourcing env directly
touch "$SCRIPT_DIR/.env"

# Create virtual environment in the project root
cd "$PROJECT_ROOT"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
. venv/bin/activate

# Set PYTHONPATH relative to project root
export PYTHONPATH="$PROJECT_ROOT/code/jockey-server"

# Install dependencies
echo "Installing dependencies - track progress in pip-install.log ..."
pip3 install -r "$SCRIPT_DIR/requirements.lock" > pip-install.log 2>&1
echo " ... dependencies installed"

# Start Jockey server in the background and save the PID
echo "Starting Jockey Server - track progress in jockey-server.log ..."
cd "$SCRIPT_DIR"  # Return to script directory for running the server
nohup python3 -m jockey server > "$PROJECT_ROOT/jockey-server.log" 2>&1 &

# Wait up to 600 seconds for the server to start
TIMEOUT=600
START_TIME=$(date +%s)

echo "Server started, awaiting final server startup confirmation..."
while ! grep -q "Application startup complete." "$PROJECT_ROOT/jockey-server.log"; do
    CURRENT_TIME=$(date +%s)
    ELAPSED_TIME=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED_TIME -ge $TIMEOUT ]; then
        echo "Startup confirmation not detected within ${TIMEOUT} seconds. Exiting."
        exit 1
    fi

    sleep 1
done

echo """Complete! Jockey is now ready to use.
You can access the server locally at http://jockey-server-langgraph-api-1:8000
It is also possible to use at <your.server>:8123 (but we do not recommend publishing IP because it is public... and we don't want people to burn through your credits this is a hackathon afterall!)
"""

# Explicitly exit after startup confirmation
exit 0
