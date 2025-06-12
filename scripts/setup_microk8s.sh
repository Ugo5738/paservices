#!/bin/bash
# MicroK8s setup script for Ubuntu ARM64
# This script installs Docker, kubectl, and MicroK8s on Ubuntu ARM64

set -e

# Print section header
section() {
  echo "===================================================================="
  echo "  $1"
  echo "===================================================================="
}

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root or with sudo"
  exit 1
fi

section "Updating System Packages"
apt-get update
apt-get upgrade -y

section "Installing Common Dependencies"
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  software-properties-common

section "Installing Docker"
# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up the stable repository for ARM64
echo \
  "deb [arch=arm64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add the current user to the docker group
if [ ! -z "$SUDO_USER" ]; then
  usermod -aG docker $SUDO_USER
  echo "Added $SUDO_USER to the docker group"
fi

# Test Docker installation
docker --version

section "Installing kubectl"
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl"
chmod +x kubectl
mv kubectl /usr/local/bin/
kubectl version --client

section "Installing MicroK8s"
# Install MicroK8s
snap install microk8s --classic --channel=1.28/stable

# Configure MicroK8s permissions
if [ ! -z "$SUDO_USER" ]; then
  usermod -a -G microk8s $SUDO_USER
  mkdir -p /home/$SUDO_USER/.kube
  chown -R $SUDO_USER:$SUDO_USER /home/$SUDO_USER/.kube
  echo "Added $SUDO_USER to the microk8s group"
fi

# Wait for MicroK8s to be ready
microk8s status --wait-ready

section "Configuring MicroK8s"
# Enable necessary addons
microk8s enable dns dashboard storage ingress

# Create an alias for kubectl
echo 'alias kubectl="microk8s kubectl"' >> /home/$SUDO_USER/.bashrc
echo 'alias k="microk8s kubectl"' >> /home/$SUDO_USER/.bashrc

# Configure kubectl to use MicroK8s
microk8s config > /home/$SUDO_USER/.kube/config
chown $SUDO_USER:$SUDO_USER /home/$SUDO_USER/.kube/config
chmod 600 /home/$SUDO_USER/.kube/config

section "Installation Complete"
echo "You need to log out and back in for the group changes to take effect"
echo "To verify installation after logging back in:"
echo "  docker --version"
echo "  kubectl version"
echo "  microk8s status"

echo "To deploy your application using kubectl:"
echo "  kubectl apply -f /path/to/your/kubernetes/manifests"
echo "To deploy using Docker Compose:"
echo "  docker compose -f /path/to/your/docker-compose.prod.yml up -d"
