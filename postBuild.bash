#!/bin/bash
# This file contains bash commands that will be executed at the end of the container build process,
# after all system packages and programming language specific package have been installed.
#
# Note: This file may be removed if you don't need to use it

# Add Docker's official GPG key:
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the docker repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker-out-of-Docker
sudo apt-get install -y jq
sudo apt-get install -y docker-ce-cli
cat <<EOM | sudo tee /etc/profile.d/docker-out-of-docker.sh > /dev/null
if ! groups workbench | grep docker > /dev/null; then
    docker_gid=\$(stat -c %g /var/host-run/docker.sock)
    sudo groupadd -g \$docker_gid docker
    sudo usermod -aG docker workbench
fi
export DOCKER_HOST="unix:///var/host-run/docker.sock"
EOM

# setup docker authentication to ngc
cat <<EOM | sudo tee /etc/profile.d/docker-ngc-auth.sh > /dev/null
if [ ! -x ~/.docker/config.json ]; then
    mkdir -p ~/.docker
    authstr=\$(echo -n '\$oauthtoken:'\$NGC_API_KEY | base64 -w 0)
    jq -n --arg key \$authstr '{"auths": {"nvcr.io": {"auth": \$key}}}' > ~/.docker/config.json
fi
EOM

# Grant user sudo access
echo "workbench ALL=(ALL) NOPASSWD:ALL" | \
    sudo tee /etc/sudoers.d/00-workbench > /dev/null


# install ngc binary
cd /opt
# commands from: https://org.ngc.nvidia.com/setup/installers/cli
if [ "$(uname -i)" == "x86_64" ]; then
  sudo wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.41.4/files/ngccli_linux.zip -O ngccli_linux.zip
else
  sudo wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.41.4/files/ngccli_arm64.zip -O ngccli_linux.zip
fi
sudo unzip ngccli_linux.zip
sudo rm ngc-cli.md5 ngccli_linux.zip
sudo chmod ugo+x ngc-cli/ngc
cat <<EOM | sudo tee /etc/profile.d/ngc-cli.sh > /dev/null
export PATH=\$PATH:/opt/ngc-cli
EOM

# custom python environment configuration
cat <<EOM | sudo tee /etc/profile.d/python.sh > /dev/null
export PATH=\$PATH:/home/workbench/.local/bin
#export PYTHONPATH=/project/code/jockey-server:/project/code/jockey-ui-demo:$PYTHONPATH
if [ ! -x /usr/bin/python ]; then sudo ln -s `which python3` /usr/bin/python; fi
EOM

# install scripts to initialize the development environment
cat <<EOM | sudo tee /etc/profile.d/init-dev-env.sh > /dev/null
if [ -f /project/code/config_sample.yaml ] && [ ! -f /project/code/config.yaml ]; then
  cp /project/code/config_sample.yaml /project/code/config.yaml &> /dev/null
fi
EOM


# brain wave collective for twelvelabs jockey 
sudo apt-get install -y python3.11
#sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
#sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2
#sudo apt-get install -y python3.11-venv python3.11-distutils

sudo apt-get install -y ffmpeg
sudo apt-get install -y python3-venv

# Add PortAudio and other audio dependencies
sudo apt-get install -y portaudio19-dev python3-dev python3-pyaudio

# Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify versions (can add this for debugging)
node --version  # Should show v20.x.x
npm --version   # Should be 10.x.x

export DEBIAN_FRONTEND=noninteractive
# Set timezone to UTC by linking the appropriate files
sudo ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime
sudo dpkg-reconfigure --frontend noninteractive tzdata
# Install tzdata without prompts
sudo apt-get install -y expect

#### NOT TESTED


# also do the mkdir & chmod for the nim dir, but not the other b/c that's out of the container 


#### Setup python virtual env 

# NOTE: cd name = repo name & not within container so this is TBD
#cd nim-anywhere && python3 -m venv venv
#source venv/bin/activate
#echo "the virtual environment is: $VIRTUAL_ENV"
#pip3 install -r requirements.txt


#### RUN 
#source venv/bin/activate
#python3 -m jockey terminal

# Create the mount for docker (/var/run)
sudo mkdir -p /var/host-run/
chmod 755 /var/host-run/

# Create a mount directory for storage ($HOME/container_storage)
sudo mkdir -p /home/workbench/container_storage
chmod 755 /home/workbench/container_storage

# Create a mount directory for Jockey video output
sudo mkdir -p /home/workbench/container_storage/jockey-output
chmod 755 /home/workbench/container_storage/jockey-output

# Provide a file to prove that the static server is healthy
echo "aok" > /home/workbench/container_storage/jockey-output/health

#Install for python
sudo apt update
pip install gradio
pip install openai
pip install requests
pip install langgraph_sdk
sudo apt update

# clean up
sudo apt-get autoremove -y
sudo rm -rf /var/cache/apt


# Finish setting up jockey and start the server
#. /project/apps/jockey.sh