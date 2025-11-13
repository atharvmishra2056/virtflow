#!/bin/bash
# Switch desktop to AMD GPU so NVIDIA can be passed through

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

echo "=== Switching Desktop to AMD GPU ==="

# 1. Create Xorg config to prefer AMD
mkdir -p /etc/X11/xorg.conf.d/

cat > /etc/X11/xorg.conf.d/10-amd-primary.conf << 'EOF'
# Force AMD GPU as primary for X server
Section "Device"
    Identifier "AMD"
    Driver "amdgpu"
    BusID "PCI:48:0:0"   # Your AMD GPU
    Option "PrimaryGPU" "yes"
EndSection

Section "Device"
    Identifier "NVIDIA"
    Driver "nvidia"
    BusID "PCI:16:0:0"   # Your NVIDIA GPU
    Option "PrimaryGPU" "no"
EndSection
EOF

echo "✓ Xorg config created"

# 2. Set environment variable for GDM/GNOME
cat > /etc/environment.d/amd-primary.conf << 'EOF'
# Use AMD GPU for Wayland/GNOME
DRI_PRIME=0
EOF

echo "✓ Environment config created"

# 3. Update GRUB to prefer AMD
if ! grep -q "amdgpu.dc=1" /etc/default/grub; then
    sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="amdgpu.dc=1 /' /etc/default/grub
    update-grub
    echo "✓ GRUB updated"
else
    echo "✓ GRUB already configured"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "⚠️  You MUST reboot for changes to take effect!"
echo ""
echo "After reboot:"
echo "  - Your desktop will use AMD GPU"
echo "  - NVIDIA GPU will be free for passthrough"
echo "  - Run VirtFlow to activate GPU"
echo ""
echo "Reboot now? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    reboot
fi
