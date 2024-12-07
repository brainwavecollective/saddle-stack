###########################################
#
#  Brain Wave Collective 
#  https://brainwavecollective.ai
# 
#    Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench.
#	 Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
#
#  File: install.sh
#  Created: 2024
#  Authors: Thienthanh Trinh & Daniel Ritchie
#
#  Copyright (c) 2024 Brain Wave Collective
###########################################

#!/bin/bash

#install.sh

set -e

#defaults
INSTALL_USER="nvwb"
INSTALL_UID="49896"
INSTALL_GID="49896"

# Parse the command-line options
while getopts "u:i:g:" opt; do
  case $opt in
    u) INSTALL_USER="$OPTARG" ;;
    i) INSTALL_UID="$OPTARG" ;;
    g) INSTALL_GID="$OPTARG" ;;
    *) echo "Usage: $0 [-u username] [-i uid] [-g gid]" >&2; exit 1 ;;
  esac
done
echo "The value of INSTALL_USER is: $INSTALL_USER"

# Set some vars
ORIGINAL_USER=$(whoami)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_FILE="/tmp/nvwb_install.log"

# Set up SUDO variable
if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

# Function for logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] (User: $(whoami)) $1"
}

# Function to check Ubuntu version
check_ubuntu_version() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [ "$ID" != "ubuntu" ]; then
            log "ERROR: AI Workbench can only be installed on Ubuntu. Your OS is $ID."
            exit 1
        fi
    else
        log "ERROR: AI Workbench can only be installed on Ubuntu. Cannot determine the operating system."
        exit 1
    fi

    version=$(lsb_release -rs)
    if [ "$version" != "22.04" ] && [ "$version" != "24.04" ]; then
        log "ERROR: AI Workbench can only be installed on Ubuntu 22.04 and 24.04, your version is: $version"
        exit 1
    else 
        log "INFO: Ubuntu version $version looks good"
    fi
}

# Function to check RAM
check_ram() {
    total_ram=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$total_ram" -lt 16 ]; then
        log "ERROR: Minimum 16 GB of RAM required. Current RAM: ${total_ram} GB"
        exit 1
    else 
        log "INFO: RAM looks good"
    fi
}

# Function to check disk space
check_disk_space() {
    available_space=$(df -BM / | awk 'NR==2 {print $4}' | sed 's/M//')
    
    if [ "$available_space" -lt 1024 ]; then
        log "ERROR: Minimum 1 GB of disk space required for basic installation. Available space: ${available_space} MB"
        exit 1
    elif [ "$available_space" -lt 30720 ]; then
        log "WARNING: AI Workbench requires at least 30 GB of disk space for containers. Available space: ${available_space} MB"
    elif [ "$available_space" -lt 40960 ]; then
        log "WARNING: AI Workbench recommends 40 GB of disk space. Available space: ${available_space} MB"
    fi
}

check_virtual() {
    virt_env=$(systemd-detect-virt)

    if [ "$virt_env" = "none" ]; then
        log "INFO: This system is not virtualized."
    elif [ "$virt_env" = "docker" ]; then
        log "ERROR: Uh oh, you're already inside of a docker container. It may be possible for you to install AI Workbench on this system, but it's unlikely, and you won't be able to use this script."
        exit 1
    elif [ "$virt_env" = "lxc" ]; then
        log "INFO: This system is running in a $virt_env container."
    else
        log "INFO: This system is running in a $virt_env virtual machine."
    fi
}

#Make sure we're not already installed 
if id "$INSTALL_USER" &>/dev/null; then
    log "WARNING: User $INSTALL_USER already exists."
	log "This is not an error because the parent script may still need to run config"
    exit 0
fi

# Main script starts here
log "Checking installation requirements..."
check_ubuntu_version
check_ram
check_disk_space
check_virtual  
log "... installation requirements check complete."

log "Updating and installing necessary packages..."
$SUDO apt update
$SUDO apt install -y pciutils sudo
log "... packages installed successfully"

# Check if Docker is installed
if command -v docker &> /dev/null; then
    log "Docker is installed. Configuring NVIDIA Container Toolkit..."
    $SUDO nvidia-ctk runtime configure --runtime=docker
    $SUDO apt install -y nvidia-container-toolkit
    $SUDO systemctl restart docker
    log "NVIDIA Container Toolkit configured"
else
    log "Docker is not installed. Skipping NVIDIA Container Toolkit configuration."
fi

# Create user and add to sudo group
if ! id "$INSTALL_USER" &>/dev/null; then
    log "Creating user $INSTALL_USER"
    $SUDO groupadd -g "$INSTALL_GID" "$INSTALL_USER"
	$SUDO useradd -m -s /bin/bash -u "$INSTALL_UID" -g "$INSTALL_GID" "$INSTALL_USER"
    $SUDO usermod -aG sudo "$INSTALL_USER"	
	
    # Add the user to the docker group if docker is installed
    if command -v docker &> /dev/null; then
        $SUDO usermod -aG docker "$INSTALL_USER"
        log "Added $INSTALL_USER to docker group"
    fi
    
    log "User $INSTALL_USER created and configured"
    
    # Add the user to the sudoers file with NOPASSWD
    log "Granting $INSTALL_USER passwordless sudo access"
    echo "$INSTALL_USER ALL=(ALL) NOPASSWD:ALL" | $SUDO tee /etc/sudoers.d/$INSTALL_USER > /dev/null
    $SUDO chmod 0440 /etc/sudoers.d/$INSTALL_USER
    log "Passwordless sudo access granted to $INSTALL_USER"
    
else
    log "User $INSTALL_USER already exists"
fi

# Set up SSH for the new user
log "Setting up SSH for $INSTALL_USER"

# Create a temporary directory with appropriate permissions
TEMP_DIR=$(mktemp -d /tmp/pubkey_transfer.XXXXXX)
if [[ ! "$TEMP_DIR" =~ ^/tmp/pubkey_transfer\. ]]; then
    log "Error: Failed to create a proper temporary directory"
    exit 1
fi
chmod 755 "$TEMP_DIR"

# Move the user-provided public key to the temporary directory
mv "${HOME}/my_public_key.pub" "$TEMP_DIR/temp_public_key.pub"
chmod 644 "$TEMP_DIR/temp_public_key.pub"

# Switch to the new user and add the key
$SUDO su - $INSTALL_USER << EOF
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
cat "$TEMP_DIR/temp_public_key.pub" >> ~/.ssh/authorized_keys
EOF

# Clean up
if [ -d "$TEMP_DIR" ] && [ "$TEMP_DIR" != "/" ] && [ "$TEMP_DIR" != "$HOME" ]; then
    rm -rf "${TEMP_DIR:?}"
else
    log "Warning: Temporary directory not found or invalid. Skipping cleanup."
fi
log "SSH setup completed for $INSTALL_USER"

# Switch to the INSTALL_USER for the rest of the script
log "Switching to user $INSTALL_USER for the remainder of the installation"
$SUDO su - $INSTALL_USER -c "$(cat << 'EOF'

# Function for logging (redefined for the new user context)
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] (User: $(whoami)) $1"
}

# Create directories for containers - ASSUMES that $HOME is /home/${INSTALL_USER}
HOST_PUBLIC_DIR="$HOME/container_storage/jockey-output"
HOST_VECTOR_DB_DIR="$HOME/container_storage/vector_db"

log "Creating installation directory: $HOST_PUBLIC_DIR"
mkdir -p "$HOST_PUBLIC_DIR"

log "Adding server health file"
echo "aok" > ${HOST_PUBLIC_DIR}/health

log "Creating installation directory: $HOST_VECTOR_DB_DIR"
mkdir -p "$HOST_VECTOR_DB_DIR"
# TBD - use named volumes instead, not sure how langsmith/workbench will respond to this but theoretically can just swap the var

# Install NVIDIA AI Workbench
INSTALL_DIR="$HOME/.nvwb/bin"
log "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

log "Downloading NVIDIA AI Workbench CLI"
curl -L https://workbench.download.nvidia.com/stable/workbench-cli/$(curl -L -s https://workbench.download.nvidia.com/stable/workbench-cli/LATEST)/nvwb-cli-$(uname)-$(uname -m) --output "$INSTALL_DIR/nvwb-cli"
chmod +x "$INSTALL_DIR/nvwb-cli"
log "NVIDIA AI Workbench CLI downloaded and made executable"
log "CLI file details: $(ls -l "$INSTALL_DIR/nvwb-cli")"

# Verify the installation directory and CLI exist
log "Verifying installation"
if [ -d "$INSTALL_DIR" ] && [ -x "$INSTALL_DIR/nvwb-cli" ]; then
    log "Installation directory and CLI verified"
else
    log "ERROR: Installation directory or CLI not found or not executable"
    log "Directory contents: $(ls -la "$INSTALL_DIR")"
    exit 1
fi

# Get the uid and gid for the INSTALL_USER
USER_UID=$(id -u)
USER_GID=$(id -g)

if [ "$USER_UID" -eq 0 ]; then
    "$INSTALL_DIR/nvwb-cli" install --accept --drivers --noninteractive --docker --gid $USER_GID --uid $USER_UID
else
    sudo -E "$INSTALL_DIR/nvwb-cli" install --accept --drivers --noninteractive --docker
fi

SERVER_IP=$(hostname -I | awk '{print $1}')

log "Installation process completed. You can now connect to this instance from your local AI Workbench client."
log "You will need to confirm your host but connection info is probably: $(whoami)@$SERVER_IP"
EOF
)"

log "Installation script finished"