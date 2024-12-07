#!/bin/bash
# destroy_remote.sh - Script to remove NVWB components from a remote server 
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
  if [[ $LOG_LEVEL == "DEBUG" ]]; then
    echo "[DEBUG] $1"
  fi
}
# Check if --destroy flag is present
if [[ "$1" != "--destroy" ]]; then
    echo "Usage: $0 --destroy"
    echo "This script will completely remove all NVWB related components from the remote server."
    exit 1
fi
# Check if SERVER_IP is set
if [[ -z "$SERVER_IP" ]]; then
    echo "Error: SERVER_IP environment variable must be set before running this script."
    echo "Please export SERVER_IP=<your_server_ip> and try again."
    exit 1
fi
echo "WARNING: This will completely destroy all NVWB related components on $SERVER_IP"
echo "This includes:"
echo "- Uninstalling NVWB components"
echo "- Stopping all services run by the nvwb user"
echo "- Removing the nvwb user"
echo "- Deleting all files in /home/nvwb"
echo
read -p "Are you sure you want to proceed? (y/yes) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi
# Read SSH key names or use defaults
WORKBENCH_KEY_NAME=${WORKBENCH_KEY_NAME:-$DEFAULT_WORKBENCH_KEY}
SERVER_KEY_NAME=${SERVER_KEY_NAME:-$DEFAULT_SERVER_KEY}
SERVER_USER=${SERVER_USER:-$DEFAULT_SERVER_USER}
echo "Starting destruction process..."
echo "Step 1: Cleaning up system components..."
ssh -i "${HOME}/.ssh/${SERVER_KEY_NAME}" "${SERVER_USER}@${SERVER_IP}" "
    # Stop all services by nvwb user
    echo 'Stopping nvwb services...'
    sudo systemctl list-units --type=service --all | grep nvwb | cut -d' ' -f1 | xargs -r sudo systemctl stop

    # Stop any docker containers owned by nvwb
    if command -v docker &>/dev/null; then
        echo 'Stopping nvwb docker containers...'
        sudo docker ps -q --filter 'label=com.nvidia.workbench' | xargs -r sudo docker stop
        sudo docker ps -qa --filter 'label=com.nvidia.workbench' | xargs -r sudo docker rm -f
    fi

    # First try graceful process termination
    echo 'Attempting graceful process termination...'
    sudo pkill -TERM -u nvwb || true
    sleep 5  # Give processes time to shut down gracefully

    # Check if processes still exist and force kill if necessary
    if sudo pgrep -u nvwb > /dev/null; then
        echo 'Some processes still running, force killing...'
        sudo pkill -KILL -u nvwb || true
        sleep 2
    fi

    # Verify no processes remain
    if sudo pgrep -u nvwb > /dev/null; then
        echo 'WARNING: Some nvwb processes still running:'
        sudo ps aux | grep nvwb
    else
        echo 'All nvwb processes stopped successfully'
    fi"

# try to run the uninstall command as nvwb user
echo "Step 2: Running NVWB uninstall..."
if ssh -i "${HOME}/.ssh/${WORKBENCH_KEY_NAME}" nvwb@${SERVER_IP} "sudo -E \$HOME/.nvwb/bin/nvwb-cli uninstall --confirm"; then
    echo "NVWB uninstall completed successfully."
else
    echo "Warning: NVWB uninstall failed or was already uninstalled."
    # Don't exit here - continue with cleanup even if uninstall fails
fi

# Now connect as server user to clean up
echo "Step 3: Cleaning up system components..."
ssh -i "${HOME}/.ssh/${SERVER_KEY_NAME}" "${SERVER_USER}@${SERVER_IP}" "
    # Remove docker volumes if they exist
    if command -v docker &>/dev/null; then
        echo 'Removing nvwb docker volumes...'
        sudo docker volume ls -q --filter 'label=com.nvidia.workbench' | xargs -r sudo docker volume rm || true
    fi

    # Remove nvwb user and home directory
    echo 'Removing nvwb user and home directory...'
    if id nvwb &>/dev/null; then
        # Clear contents first to avoid busy file handles
        if [ -d /home/nvwb ]; then
            sudo find /home/nvwb -type f -exec rm -f {} + 2>/dev/null || true
        fi
        
		sudo userdel -r nvwb || {
			echo 'Failed initial removal, attempting aggressive cleanup...'
			sudo pkill -9 -u nvwb
			sleep 2
			sudo rm -rf /home/nvwb
			sudo userdel -f nvwb || {
				echo 'Force removal failed, trying last resort...'
				sudo rm -rf /home/nvwb /var/mail/nvwb
				sudo sed -i '/^nvwb:/d' /etc/passwd /etc/shadow /etc/group
				
				# Check if last resort worked
				if ! grep -q '^nvwb:' /etc/passwd && \
				   ! grep -q '^nvwb:' /etc/shadow && \
				   ! grep -q '^nvwb:' /etc/group && \
				   ! id nvwb &>/dev/null; then
					echo "Last resort cleanup successful"
				else
					echo "WARNING: User nvwb still exists in system files"
					exit 1
				fi
			}
		}
        echo 'nvwb user removed successfully.'
    else
        echo 'nvwb user does not exist.'
    fi

    # Final cleanup
    echo 'Performing final cleanup...'
    sudo rm -rf /home/nvwb 2>/dev/null || true
    sudo rm -rf /tmp/nvwb-* 2>/dev/null || true
    sudo rm -f /etc/sudoers.d/nvwb 2>/dev/null || true

    # Verify cleanup
    if id nvwb &>/dev/null; then
        echo 'WARNING: nvwb user still exists after cleanup'
    fi
    if [ -d /home/nvwb ]; then
        echo 'WARNING: /home/nvwb directory still exists after cleanup'
    fi"

echo
echo "Destruction process complete."
echo "All NVWB components have been removed from $SERVER_IP"