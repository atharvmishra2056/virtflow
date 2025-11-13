#!/bin/bash
# Install libvirt hooks for GPU passthrough management

set -e

echo "Installing libvirt hooks for GPU passthrough..."

# Create hooks directory if it doesn't exist
sudo mkdir -p /etc/libvirt/hooks

# Create the qemu hook script
cat << 'EOF' | sudo tee /etc/libvirt/hooks/qemu > /dev/null
#!/bin/bash
# Libvirt QEMU hook for GPU passthrough management
# This hook is called by libvirt when VM state changes

GUEST_NAME="$1"
OPERATION="$2"
SUB_OPERATION="$3"

LOG_FILE="/var/log/libvirt/qemu-hook.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$GUEST_NAME] $1" >> "$LOG_FILE"
}

# Check if VM has GPU passthrough (look for hostdev in XML)
has_gpu_passthrough() {
    virsh dumpxml "$GUEST_NAME" 2>/dev/null | grep -q '<hostdev.*type=.pci'
}

log "Hook called: operation=$OPERATION sub_operation=$SUB_OPERATION"

# Only act on VMs with GPU passthrough
if ! has_gpu_passthrough; then
    log "No GPU passthrough detected, skipping"
    exit 0
fi

case "$OPERATION" in
    "prepare")
        case "$SUB_OPERATION" in
            "begin")
                log "VM starting - GPU should already be bound to VFIO"
                # GPU binding is done during activation, not here
                ;;
        esac
        ;;
    
    "release")
        case "$SUB_OPERATION" in
            "end")
                log "VM stopped - GPU will be restored to host by vm_controller"
                # GPU unbinding is handled by vm_controller.py
                ;;
        esac
        ;;
esac

exit 0
EOF

# Make hook executable
sudo chmod +x /etc/libvirt/hooks/qemu

# Create log directory
sudo mkdir -p /var/log/libvirt
sudo touch /var/log/libvirt/qemu-hook.log
sudo chmod 666 /var/log/libvirt/qemu-hook.log

# Restart libvirtd to load hooks
echo "Restarting libvirtd..."
sudo systemctl restart libvirtd

echo "✓ Libvirt hooks installed successfully"
echo "  Hook script: /etc/libvirt/hooks/qemu"
echo "  Log file: /var/log/libvirt/qemu-hook.log"
