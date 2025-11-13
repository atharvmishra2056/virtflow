#!/bin/bash
# Updated: VirtFlow Dev Env Setup (Ubuntu 25.10, latest packages)

set -e

echo "=== VirtFlow Development Setup ==="

# Detect Ubuntu version
if [ -f /etc/os-release ]; then
   . /etc/os-release
   echo "Detected: $NAME $VERSION"
fi

echo "Installing system dependencies..."
sudo apt update

# Use latest Python available (likely 3.12+)
sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    libvirt-dev \
    libvirt-daemon-system \
    libvirt-clients \
    qemu-system-x86 \
    qemu-utils \
    virt-manager \
    bridge-utils

# Add user to correct groups
echo "Adding $USER to libvirt and kvm groups (if available)..."
sudo usermod -aG libvirt $USER
sudo usermod -aG kvm $USER || true  # kvm group may not always exist on desktops

echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Enabling libvirtd service..."
sudo systemctl enable --now libvirtd

echo "=== Setup Complete ==="
echo "Please log out/in for group changes (libvirt)."
echo "Activate venv: source venv/bin/activate"
echo "Run: python src/main.py"
