#!/bin/bash
# Complete GPU passthrough setup script for VirtFlow

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== VirtFlow GPU Passthrough Setup ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

# 1. Check IOMMU
echo -e "${YELLOW}[1/6] Checking IOMMU...${NC}"
if dmesg | grep -q "IOMMU"; then
    echo -e "${GREEN}✓ IOMMU is enabled${NC}"
else
    echo -e "${RED}✗ IOMMU is NOT enabled${NC}"
    echo "  Add 'intel_iommu=on' or 'amd_iommu=on' to GRUB_CMDLINE_LINUX in /etc/default/grub"
    echo "  Then run: sudo update-grub && sudo reboot"
    exit 1
fi

# 2. Load VFIO modules
echo -e "${YELLOW}[2/6] Loading VFIO modules...${NC}"
modprobe vfio
modprobe vfio_iommu_type1
modprobe vfio_pci
echo -e "${GREEN}✓ VFIO modules loaded${NC}"

# 3. Add VFIO modules to load at boot
echo -e "${YELLOW}[3/6] Configuring VFIO modules for boot...${NC}"
cat > /etc/modules-load.d/vfio.conf << EOF
vfio
vfio_iommu_type1
vfio_pci
EOF
echo -e "${GREEN}✓ VFIO modules will load at boot${NC}"

# 4. Install libvirt hooks
echo -e "${YELLOW}[4/6] Installing libvirt hooks...${NC}"
mkdir -p /etc/libvirt/hooks

cat > /etc/libvirt/hooks/qemu << 'EOF'
#!/bin/bash
# Libvirt QEMU hook for GPU passthrough management

GUEST_NAME="$1"
OPERATION="$2"
SUB_OPERATION="$3"

LOG_FILE="/var/log/libvirt/qemu-hook.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$GUEST_NAME] $1" >> "$LOG_FILE"
}

# Check if VM has GPU passthrough
has_gpu_passthrough() {
    virsh dumpxml "$GUEST_NAME" 2>/dev/null | grep -q '<hostdev.*type=.pci'
}

log "Hook called: operation=$OPERATION sub_operation=$SUB_OPERATION"

if ! has_gpu_passthrough; then
    log "No GPU passthrough detected, skipping"
    exit 0
fi

case "$OPERATION" in
    "prepare")
        case "$SUB_OPERATION" in
            "begin")
                log "VM starting - GPU should already be bound to VFIO"
                ;;
        esac
        ;;
    
    "release")
        case "$SUB_OPERATION" in
            "end")
                log "VM stopped - GPU will be restored to host by vm_controller"
                ;;
        esac
        ;;
esac

exit 0
EOF

chmod +x /etc/libvirt/hooks/qemu
mkdir -p /var/log/libvirt
touch /var/log/libvirt/qemu-hook.log
chmod 666 /var/log/libvirt/qemu-hook.log
echo -e "${GREEN}✓ Libvirt hooks installed${NC}"

# 5. Setup sudo permissions (CRITICAL!)
echo -e "${YELLOW}[5/7] Setting up passwordless sudo for GPU operations...${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run sudo permissions setup
if [ -f "$SCRIPT_DIR/setup_sudo_permissions.sh" ]; then
    bash "$SCRIPT_DIR/setup_sudo_permissions.sh"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Sudo permissions configured${NC}"
    else
        echo -e "${RED}✗ Failed to setup sudo permissions${NC}"
        echo "  GPU binding may require password"
    fi
else
    echo -e "${YELLOW}⚠ Sudo permissions script not found${NC}"
    echo "  You may need to enter password for GPU operations"
fi

# 6. Configure libvirt for GPU passthrough
echo -e "${YELLOW}[6/7] Configuring libvirt...${NC}"
# Ensure user is in libvirt group
ACTUAL_USER="${SUDO_USER:-$USER}"
usermod -aG libvirt "$ACTUAL_USER" 2>/dev/null || true
echo -e "${GREEN}✓ User added to libvirt group${NC}"

# 7. Restart libvirtd
echo -e "${YELLOW}[7/7] Restarting libvirtd...${NC}"
systemctl restart libvirtd
echo -e "${GREEN}✓ Libvirtd restarted${NC}"

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Log out and log back in (for group changes)"
echo "  2. Run VirtFlow application"
echo "  3. Select a VM and click 'Activate GPU'"
echo "  4. Start the VM - dGPU will disconnect from host"
echo "  5. Stop the VM - dGPU will reconnect to host"
echo ""
echo "Logs:"
echo "  - Libvirt hook: /var/log/libvirt/qemu-hook.log"
echo "  - VirtFlow app: app_debug.log"
