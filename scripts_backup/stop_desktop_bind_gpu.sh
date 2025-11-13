#!/bin/bash
# DANGEROUS: Stop desktop, bind GPU, you'll lose GUI temporarily

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

echo "⚠️  ⚠️  ⚠️  WARNING ⚠️  ⚠️  ⚠️"
echo ""
echo "This will:"
echo "  1. Stop your desktop (you'll lose GUI)"
echo "  2. Bind NVIDIA GPU to VFIO"
echo "  3. You'll need to SSH in or switch to TTY to restart desktop"
echo ""
echo "Only use this for testing!"
echo ""
echo "Continue? (type 'yes' to proceed)"
read -r response

if [ "$response" != "yes" ]; then
    echo "Aborted"
    exit 0
fi

echo "Stopping desktop in 5 seconds..."
sleep 5

# Stop display manager
echo "Stopping GDM..."
systemctl stop gdm3 || systemctl stop gdm || true

sleep 2

# Kill any remaining processes using nvidia
echo "Killing processes using NVIDIA..."
fuser -k /dev/nvidia* 2>/dev/null || true
sleep 1

# Unload nvidia modules
echo "Removing NVIDIA modules..."
modprobe -r nvidia_drm nvidia_modeset nvidia_uvm nvidia || true

sleep 1

# Bind GPU to VFIO
echo "Binding GPU to VFIO..."
cd /home/atharv/virtflow
python3 src/backend/gpu_worker.py bind 0000:10:00.0|10de|2582 0000:10:00.1|10de|2291

# Check result
if lspci -k -s 10:00.0 | grep -q "vfio-pci"; then
    echo ""
    echo "✓ SUCCESS! GPU bound to VFIO"
    echo ""
    echo "To restart desktop:"
    echo "  sudo systemctl start gdm3"
    echo ""
    echo "Or from TTY (Ctrl+Alt+F3):"
    echo "  sudo systemctl start gdm3"
else
    echo ""
    echo "✗ FAILED to bind GPU"
    echo ""
    echo "Restarting desktop..."
    systemctl start gdm3 || systemctl start gdm
fi
