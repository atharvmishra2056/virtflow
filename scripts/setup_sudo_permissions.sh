#!/bin/bash
# Setup passwordless sudo for GPU passthrough operations

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

ACTUAL_USER="${SUDO_USER:-$USER}"
echo "Setting up sudo permissions for user: $ACTUAL_USER"

# Create sudoers file for VirtFlow
cat > /etc/sudoers.d/virtflow-gpu << EOF
# VirtFlow GPU Passthrough - Passwordless sudo for specific operations
# Created: $(date)

# Allow tee for GPU binding (used to write to sysfs)
$ACTUAL_USER ALL=(root) NOPASSWD: /usr/bin/tee

# Allow sh for sysfs writes (more reliable than tee for driver binding)
$ACTUAL_USER ALL=(root) NOPASSWD: /usr/bin/sh
$ACTUAL_USER ALL=(root) NOPASSWD: /bin/sh

# Allow module operations (modprobe paths)
$ACTUAL_USER ALL=(root) NOPASSWD: /usr/sbin/modprobe
$ACTUAL_USER ALL=(root) NOPASSWD: /sbin/modprobe

# Allow pkill for killing GPU processes
$ACTUAL_USER ALL=(root) NOPASSWD: /usr/bin/pkill

# Allow reading dmesg
$ACTUAL_USER ALL=(root) NOPASSWD: /usr/bin/dmesg
EOF

# Set correct permissions
chmod 0440 /etc/sudoers.d/virtflow-gpu

# Verify sudoers file is valid
if visudo -c -f /etc/sudoers.d/virtflow-gpu; then
    echo "✓ Sudoers file created successfully"
    echo "  File: /etc/sudoers.d/virtflow-gpu"
    echo "  User '$ACTUAL_USER' can now run GPU binding commands without password"
else
    echo "✗ ERROR: Sudoers file has syntax errors!"
    rm -f /etc/sudoers.d/virtflow-gpu
    exit 1
fi

echo ""
echo "Test passwordless sudo:"
echo "  sudo -n tee /sys/bus/pci/drivers_probe <<< test"
echo ""
echo "If it doesn't ask for password, setup is successful!"
