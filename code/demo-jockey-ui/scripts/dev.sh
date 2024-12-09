###########################################
#
#  Brain Wave Collective 
#  https://brainwavecollective.ai
# 
#    Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench.
#	 Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
#
#  File: dev.sh
#  Created: 2024
#  Authors: Thienthanh Trinh & Daniel Ritchie
#
#  Copyright (c) 2024 Brain Wave Collective
###########################################

#!/bin/bash
# /scripts/dev.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_NAME="jockey-ui"  # Get this from environment.yml if exist
PARENT_ENV="$SCRIPT_DIR/../../../.env"
LOCAL_ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
LOCAL_ENV="$PROJECT_ROOT/.env"

# Check if required files exist
if [[ ! -f "$PARENT_ENV" ]]; then
    echo "Parent .env file not found at $PARENT_ENV"
    exit 1

fi

if [[ ! -f "$LOCAL_ENV_EXAMPLE" ]]; then
    echo "Local .env.example file not found at $LOCAL_ENV_EXAMPLE"
    exit 1
fi

# Create a temporary file
temp_env=$(mktemp)

# Read .env.example and process each line
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip comments and empty lines
    if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
        echo "$line" >> "$temp_env"
        continue
    fi

    # Extract the key from .env.example (everything before =)
    key=$(echo "$line" | cut -d'=' -f1)

    # If key is empty, skip
    if [[ -z "$key" ]]; then
        echo "$line" >> "$temp_env"
        continue
    fi

    # Look for the key in the parent .env file
    parent_value=$(grep "^${key}=" "$PARENT_ENV" | cut -d'=' -f2-)

    if [[ -n "$parent_value" ]]; then
        # Key found in parent .env, use its value
        echo "${key}=${parent_value}" >> "$temp_env"
    else
        # Key not found in parent .env, keep the example value
        echo "$line" >> "$temp_env"
    fi
done < "$LOCAL_ENV_EXAMPLE"

# Move temporary file to .env
mv "$temp_env" "$LOCAL_ENV"

# Set appropriate permissions
chmod 600 "$LOCAL_ENV"



# Set VITE_TWELVE_LABS_INDEX_ID
export VITE_TWELVE_LABS_INDEX_ID="${TWELVE_LABS_INDEX_ID}"

# Check if conda is available and in PATH
if ! command -v conda &> /dev/null; then
    echo "Error: conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first"
    exit 1
fi

# Function to ensure conda environment exists and is properly configured
function ensure_conda_env() {
    if ! conda info --envs | grep -q "^${ENV_NAME}"; then
        # Check for conda-lock file first
        if [ -f "conda-lock.yml" ]; then
            echo "Found conda-lock.yml, creating environment from lock file..."
            conda-lock install --name "${ENV_NAME}" conda-lock.yml
        else
            echo "Error: Must use conda-lock.yml for this process"
            exit 1
        fi
    else
        echo "Conda environment ${ENV_NAME} already exists"
    fi
}

# Function to start development servers
function start_dev_servers() {
    echo "Starting development servers..."
    
    # Start Vite in background
    echo "Starting Vite development server..."
    npm run dev &
    VITE_PID=$!
    
    # Start FastAPI
    echo "Starting FastAPI server..."
    uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
    
    # Cleanup on exit
    trap 'kill $VITE_PID' EXIT
}

cd "$PROJECT_ROOT"
echo """
---------------------------------------------------------------------------------------------------
Starting development environment in: $(pwd)
---------------------------------------------------------------------------------------------------
"""

# Ensure conda environment exists
ensure_conda_env

# Activate conda environment
echo "Activating conda environment: ${ENV_NAME}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${ENV_NAME}" || {
    echo "Error: Failed to activate conda environment"
    exit 1
}

# Check for node_modules
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    yarn install --frozen-lockfile || {
        echo "Error: yarn install failed"
        exit 1
    }
fi

# Start development servers
start_dev_servers
