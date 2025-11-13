#!/bin/bash
# One-time setup for VirtFlow GPU passthrough permissions

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

USERNAME=${SUDO_USER:-$USER}

echo "Setting up VFIO permissions for user: $USERNAME"

# Create sudoers file
cat > /etc/sudoers.d/virtflow << EOF
# VirtFlow GPU Passthrough Permissions
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/fuser *
$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/kill *
$USERNAME ALL=(ALL) NOPASSWD: /sbin/modprobe *
$USERNAME ALL=(ALL) NOPASSWD: /sbin/rmmod *
EOF

chmod 0440 /etc/sudoers.d/virtflow

echo "✓ Permissions configured"
echo ""
echo "Now you can use VirtFlow without password prompts!"
echo "Just click 'Activate GPU' button and it will:"
echo "  1. Kill gnome-shell and GPU processes"
echo "  2. Unbind NVIDIA driver"
echo "  3. Bind GPU to VFIO"
echo "  4. Everything automatic!"
echo ""
