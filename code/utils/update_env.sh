###########################################
#
#  Brain Wave Collective
#  https://brainwavecollective.ai
# 
#    Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench.
#	 Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
#
#  File: update_env.sh
#  Created: 2024
#  Authors: Thienthanh Trinh & Daniel Ritchie
#
#  Copyright (c) 2024 Brain Wave Collective
###########################################

#!/bin/bash
# This update_env.sh script manages NVIDIA Workbench environment configuration including secrets, 
# environment variables, and mounts


# Exit on any error
set -e

# Initialize error flag
has_missing_vars=0

# Determine the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if .env file exists in the parent directory of the script location
if [[ -f "$SCRIPT_DIR/../../.env" ]]; then
  # Source the .env file
  source "$SCRIPT_DIR/../../.env"
  echo "Loaded environment variables from $SCRIPT_DIR/../.env"
else
  echo ".env file not found in $SCRIPT_DIR/../"
fi

# Check if NVWB_PROJECT_PATH is set
if [ -z "${NVWB_PROJECT_PATH}" ]; then
    echo "Error: NVWB_PROJECT_PATH must be set"
    exit 1
fi

# Function to check if a variable is set
check_variable() {
    local var_name="$1"
    if [ -z "${!var_name}" ]; then
        echo "Error: ${var_name} is not set"
        return 1
    fi
    return 0
}

# Function to configure a secret
configure_secret() {
    local var_name="$1"
    local var_value="${!var_name}"
    echo "Configuring secret: ${var_name}"
    ${NVWB_BIN_PATH} configure secrets "${var_name}:${var_value}" 
}

# Function to configure an environment variable
configure_env_var() {
    local var_name="$1"
    local var_value="${!var_name}"
    echo "Configuring environment variable: ${var_name} with value ${var_value}"
	
    # First try to delete if it exists (ignoring errors if it doesn't)
    ${NVWB_BIN_PATH} delete environment-variable "${var_name}" 2>/dev/null || true
	echo "Deleted existing var"

    # Create new environment variable
    ${NVWB_BIN_PATH} create environment-variable "${var_name}" "${var_value}"
}

# Set context
export NVWB_CONTEXT="local"

# Check required API keys (these will be set as secrets)
required_secrets=(
    "TWELVE_LABS_API_KEY"
    "OPENAI_API_KEY"
    "LANGSMITH_API_KEY"
)

# Check all required secrets
echo "Checking required secrets..."
for secret in "${required_secrets[@]}"; do
    if ! check_variable "$secret"; then
        has_missing_vars=1
    fi
done

# Check all required environment variables
echo "Checking required environment variables..."
for var in "${required_env_vars[@]}"; do
    if ! check_variable "$var"; then
        has_missing_vars=1
    fi
done

# Exit if any variables are missing
if [ $has_missing_vars -eq 1 ]; then
    echo "Exiting due to missing required variables"
    exit 1
fi

# Configure all secrets
echo "Configuring secrets..."
for secret in "${required_secrets[@]}"; do
    configure_secret "$secret"
done

# Configure all environment variables
echo "Configuring environment variables..."
for var in "${required_env_vars[@]}"; do
    configure_env_var "$var"
done

# Configure mounts
echo "Configuring mounts..."
${NVWB_BIN_PATH} configure mounts "/var/run/:/var/host-run/" "/home/nvwb/container_storage/:/home/nvwb/container_storage/"

# Main restart logic
echo "Restarting environment..."

# Try to stop the container
if check_container_status; then
    echo "Stopping existing container..."
    if ! ${NVWB_BIN_PATH} stop --container; then
        echo "Unable to stop the container. This may be OK if it is not running"
    fi
fi

# Start the container
echo "Starting container..."
if ! ${NVWB_BIN_PATH} start --container; then
    echo "Unable to stop the container. This is OK on a new environment that has not finished building."
fi

echo "Environment configuration completed successfully"
exit 0