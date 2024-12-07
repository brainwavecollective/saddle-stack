###########################################
#
#  Brain Wave Collective
#  https://brainwavecollective.ai
# 
#    Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench.
#	 Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
#
#  File: configure_remote.sh
#  Created: 2024
#  Authors: Thienthanh Trinh & Daniel Ritchie
#
#  Copyright (c) 2024 Brain Wave Collective
###########################################

#!/bin/bash

#configure_remote.sh

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

LOG_LEVEL=${LOG_LEVEL:-INFO}

# Function to output debug info
debug_info() {
  if [[ $LOG_LEVEL == "DEBUG"  ]]; then
    echo "[DEBUG] $1"
  fi
}

# Start of the script
debug_info "Script started."

# Define all configurable variables with their defaults
declare -A CONFIG_VARS=(
  ["SERVER_IP"]=""                  # Required, no default
  ["SERVER_KEY_NAME"]="$DEFAULT_SERVER_KEY"
  ["WORKBENCH_KEY_NAME"]="$DEFAULT_WORKBENCH_KEY"
  ["SERVER_USER"]="$DEFAULT_SERVER_USER"
  ["GITHUB_USER"]=""               # Will try git config if not set
  ["GITHUB_PAT"]="$GITHUB_PAT"               # Required, default to env var
  ["TWELVE_LABS_API_KEY"]="$TWELVE_LABS_API_KEY"      # Required, default to env var
  ["OPENAI_API_KEY"]="$OPENAI_API_KEY"          # Required, default to env var
  ["LANGSMITH_API_KEY"]="$LANGSMITH_API_KEY"       # Required, default to env var
  ["LOG_LEVEL"]="INFO"                  # Optional, defaults to 0
)

# Print all configurable variables
echo "Configurable variables for this script:"
for var in "${!CONFIG_VARS[@]}"; do
  if [[ -n "${CONFIG_VARS[$var]}" ]]; then
    echo "- $var"
    debug_info "  default: ${CONFIG_VARS[$var]}"
  else
    echo "- $var (required)"
  fi
done
echo

# Check if SERVER_IP is set
if [[ -z "$SERVER_IP" ]]; then
  echo "Error: SERVER_IP environment variable must be set before running this script."
  echo "Please export SERVER_IP=<your_server_ip> and try again."
  exit 1
fi

# Prompt for SSH key names or use defaults
read -p "Enter the name of your server private key (default: $DEFAULT_SERVER_KEY): " SERVER_KEY_NAME
SERVER_KEY_NAME=${SERVER_KEY_NAME:-$DEFAULT_SERVER_KEY}

read -p "Enter the name of your workbench private key (default: $DEFAULT_WORKBENCH_KEY): " WORKBENCH_KEY_NAME
WORKBENCH_KEY_NAME=${WORKBENCH_KEY_NAME:-$DEFAULT_WORKBENCH_KEY}

# Prompt for server username or use default
read -p "Enter the server username (default: $DEFAULT_SERVER_USER): " SERVER_USER
SERVER_USER=${SERVER_USER:-$DEFAULT_SERVER_USER}
debug_info "Using server username: $SERVER_USER"

# Check required environment variables
debug_info "Checking required environment variables..."
MISSING_VARS=()

# Function to check if a variable is set
check_var() {
  if [[ -z "${!1}" ]]; then
    MISSING_VARS+=("$1")
    debug_info "Missing variable: $1"
  else
    debug_info "Variable $1 is set: ${!1}"
  fi
}

# Function to check if a file exists
check_file() {
  local file_path="${1/#\~/$HOME}" # Expand tilde to home directory
  if [[ ! -f "$file_path" ]]; then
    MISSING_FILES+=("$file_path")
    debug_info "Missing file: $file_path"
  else
    debug_info "File $file_path exists."
  fi
}

# Check required variables
check_var "TWELVE_LABS_API_KEY"
check_var "OPENAI_API_KEY"
check_var "LANGSMITH_API_KEY"

# Check required SSH key files
debug_info "Checking required files..."
MISSING_FILES=()

# Check both private and public keys for server access
check_file "~/.ssh/$SERVER_KEY_NAME"
check_file "~/.ssh/$SERVER_KEY_NAME.pub"

# Check both private and public keys for workbench access
check_file "~/.ssh/$WORKBENCH_KEY_NAME"
check_file "~/.ssh/$WORKBENCH_KEY_NAME.pub"

# Report missing variables and files
if [[ ${#MISSING_VARS[@]} -ne 0 || ${#MISSING_FILES[@]} -ne 0 ]]; then
  echo "Error: The following required items are missing:"
  
  if [[ ${#MISSING_VARS[@]} -ne 0 ]]; then
    echo "Missing environment variables:"
    for VAR in "${MISSING_VARS[@]}"; do
      echo "  - $VAR"
    done
  fi

  if [[ ${#MISSING_FILES[@]} -ne 0 ]]; then
    echo "Missing files:"
    for FILE in "${MISSING_FILES[@]}"; do
      echo "  - $FILE"
    done
  fi

  echo "Please ensure all required variables are set and files are present before re-running the script."
  exit 1
fi

debug_info "All required environment variables and files are present."
debug_info "SERVER_IP is: $SERVER_IP"

# First try to get GITHUB_USER from environment, then from git config
GITHUB_USER=${GITHUB_USER:-$(git config --get github.user)}
if [[ -z "$GITHUB_USER" ]]; then
  read -p "Enter GITHUB_USER: " GITHUB_USER
else
  echo "Your GitHub username is set: $GITHUB_USER"
  read -p "Do you want to edit this value? (current: $GITHUB_USER) [y/N]: " edit_choice
  if [[ "$edit_choice" =~ ^[Yy]$ ]]; then
    read -p "Enter GITHUB_USER: " GITHUB_USER
  fi
fi
debug_info "GITHUB_USER is set: $GITHUB_USER"

# Masking GITHUB_PAT for security
if [[ -z "$GITHUB_PAT" ]]; then
  read -s -p "Enter GITHUB_PAT: " GITHUB_PAT
  echo
else
  debug_info "GITHUB_PAT detected: ${GITHUB_PAT:0:3}****${GITHUB_PAT: -3}"
fi

# Debug SSH setup
debug_info "Executing SCP command to copy SSH public key..."
scp -i "${HOME}/.ssh/$SERVER_KEY_NAME" "${HOME}/.ssh/$WORKBENCH_KEY_NAME.pub" ${SERVER_USER}@${SERVER_IP}:~/my_public_key.pub

debug_info "Setting up the remote service via SSH..."
ssh -i "${HOME}/.ssh/${SERVER_KEY_NAME}" "${SERVER_USER}@${SERVER_IP}" "
  GITHUB_USER='${GITHUB_USER}'
  GITHUB_PAT='${GITHUB_PAT}'
  URL='https://raw.githubusercontent.com/brainwavecollective/nvwb-tl-jockey/main/code/utils/install.sh'
  
  echo 'Debugging on the remote server...'
  
  # Validate environment variables
  if [[ -z \"\${GITHUB_USER}\" || -z \"\${GITHUB_PAT}\" ]]; then
    echo 'Error: GITHUB_USER or GITHUB_PAT is not set.'
    exit 1
  fi
  
  echo \"[DEBUG] GITHUB_USER=\${GITHUB_USER}\"
  echo '[DEBUG] GITHUB_PAT is set.'
  echo \"[DEBUG] URL=\${URL}\"
  
  echo 'Removing existing script'
  rm -f install.sh
  
  # Download the install script with proper error handling
  curl -f -S -L \
    -H 'Cache-Control: no-cache, no-store, must-revalidate' \
    -H \"Authorization: token \${GITHUB_PAT}\" \
    -o install.sh \
    \"\${URL}\" || {
      echo \"Error: Failed to fetch \${URL}. Please check the URL and credentials.\"
      exit 1
    }
    
  # Verify file was downloaded and has content
  if [[ ! -s 'install.sh' ]]; then
    echo 'Downloaded file is empty or missing.'
    exit 1
  fi
  
  chmod +x install.sh
  ./install.sh
"

# TBD: automatically setup the remote (if it doesn't already exist)
debug_info "Server preparation complete. Setup your NVIDIA AI Workbench remote with these details:"
echo -e "
Location Name & Description: Your choosing
Hostname or IP Address: $SERVER_IP
SSH Port: 22
SSH Username: nvwb
SSH Keyfile: ~/.ssh/$WORKBENCH_KEY_NAME
Workbench Directory: (use default)

... and then create a cloning this repo to create the project: 
https://github.com/brainwavecollective/saddle-stack.git
"
read -p "Press Enter after you have established a connection to your remote and cloned the repo..."

# TBD: automatically clone the project on the remote (assume it doesn't exist, check and give option to delete it)


# Final remote setup
debug_info "Running final setup commands on the server..."
ssh -i ${HOME}/.ssh/${WORKBENCH_KEY_NAME} nvwb@${SERVER_IP} \
  "export NVWB_BIN_PATH='/home/nvwb/.nvwb/bin/nvwb-cli' && \
  export NVWB_PROJECT_PATH='/home/nvwb/nvidia-workbench/brainwavecollective-saddle-stack' && \
  sed -i 's/nvwb /\${NVWB_BIN_PATH} /g' \"\${NVWB_PROJECT_PATH}/code/utils/update_env.sh\" && \
  TWELVE_LABS_API_KEY='$TWELVE_LABS_API_KEY' \
  OPENAI_API_KEY='$OPENAI_API_KEY' \
  LANGSMITH_API_KEY='$LANGSMITH_API_KEY' \
  bash \"\${NVWB_PROJECT_PATH}/code/utils/update_env.sh\""

debug_info "Final setup complete."