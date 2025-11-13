#!/bin/bash
# Quick test script for Looking Glass

echo "Testing Looking Glass with SPICE connection..."
echo ""

# Get SPICE URI
SPICE_URI=$(virsh domdisplay Windows11)
echo "SPICE URI: $SPICE_URI"

# Extract host:port
SPICE_HOST_PORT=$(echo "$SPICE_URI" | sed 's/spice:\/\///')
echo "SPICE Host:Port: $SPICE_HOST_PORT"

# Extract host and port separately
SPICE_HOST=$(echo "$SPICE_HOST_PORT" | cut -d: -f1)
SPICE_PORT=$(echo "$SPICE_HOST_PORT" | cut -d: -f2)

# Launch Looking Glass
echo ""
echo "Launching Looking Glass..."
echo "Command: looking-glass-client -f /dev/shm/looking-glass spice:host=$SPICE_HOST spice:port=$SPICE_PORT"
echo ""

looking-glass-client -f /dev/shm/looking-glass \
    spice:host="$SPICE_HOST" \
    spice:port="$SPICE_PORT" \
    -o win:borderless=no \
    -o win:minimize=yes \
    -o win:maximize=yes

echo ""
echo "=========================================="
echo "MOUSE CONTROL (IMPORTANT!):"
echo "=========================================="
echo "  • Press ScrollLock to CAPTURE mouse"
echo "  • Press ScrollLock again to RELEASE mouse"
echo "  • DO NOT click window - use ScrollLock only!"
echo ""
echo "If mouse gets stuck:"
echo "  • Press ScrollLock to release"
echo "  • Or press Ctrl+Alt+Q to quit"
echo "=========================================="
