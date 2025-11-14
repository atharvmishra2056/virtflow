#!/bin/bash
# Looking Glass Client Installation Script
# Builds and installs Looking Glass from source

set -e  # Exit on error

echo "=========================================="
echo "Looking Glass Client Installation Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Please do not run as root. Run as normal user.${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing build dependencies...${NC}"
sudo apt update
sudo apt install -y \
    binutils-dev \
    cmake \
    fonts-dejavu-core \
    libfontconfig-dev \
    gcc \
    g++ \
    pkg-config \
    libegl-dev \
    libgl-dev \
    libgles-dev \
    libspice-protocol-dev \
    nettle-dev \
    libx11-dev \
    libxcursor-dev \
    libxi-dev \
    libxinerama-dev \
    libxpresent-dev \
    libxss-dev \
    libxkbcommon-dev \
    libwayland-dev \
    wayland-protocols \
    libpipewire-0.3-dev \
    libpulse-dev \
    libsamplerate0-dev \
    git \
    wget \
    libdecor-0-dev # <--- ADD THIS LINE

echo ""
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Create build directory
BUILD_DIR="$HOME/looking-glass-build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo -e "${YELLOW}Step 2: Downloading Looking Glass source...${NC}"

# Remove old clone if exists
if [ -d "LookingGlass" ]; then
    echo "Removing old source directory..."
    rm -rf LookingGlass
fi

# Clone the correct repository
git clone --recursive https://github.com/gnif/LookingGlass.git
cd LookingGlass

echo ""
echo -e "${GREEN}✓ Source downloaded${NC}"
echo ""

# Get latest stable version
echo -e "${YELLOW}Step 3: Checking out latest stable version...${NC}"
LATEST_TAG=$(git describe --tags --abbrev=0)
echo "Latest stable version: $LATEST_TAG"
git checkout "$LATEST_TAG"
git submodule update --init --recursive

echo ""
echo -e "${GREEN}✓ Checked out $LATEST_TAG${NC}"
echo ""

echo -e "${YELLOW}Step 4: Building Looking Glass client...${NC}"
cd client
mkdir -p build
cd build

# Configure with cmake
cmake ../ \
    -DENABLE_WAYLAND=ON \
    -DENABLE_X11=ON \
    -DENABLE_PIPEWIRE=ON \
    -DENABLE_PULSEAUDIO=ON \
    -DENABLE_LIBDECOR=ON # <--- ADD THIS LINE

# Build (use all CPU cores)
make -j$(nproc)

echo ""
echo -e "${GREEN}✓ Build completed${NC}"
echo ""

echo -e "${YELLOW}Step 5: Installing Looking Glass client...${NC}"
sudo make install

# Update library cache
sudo ldconfig

echo ""
echo -e "${GREEN}✓ Looking Glass client installed${NC}"
echo ""

# Verify installation
if command -v looking-glass-client &> /dev/null; then
    VERSION=$(looking-glass-client --version 2>&1 | head -n1 || echo "unknown")
    echo -e "${GREEN}✓ Installation verified: $VERSION${NC}"
else
    echo -e "${RED}✗ Installation verification failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 6: Setting up shared memory file...${NC}"

# Create shared memory file
sudo touch /dev/shm/looking-glass
sudo truncate -s 128M /dev/shm/looking-glass
sudo chown libvirt-qemu:kvm /dev/shm/looking-glass
sudo chmod 660 /dev/shm/looking-glass

# Make it persistent across reboots
echo "f /dev/shm/looking-glass 0660 libvirt-qemu kvm 128M" | sudo tee /etc/tmpfiles.d/10-looking-glass.conf

echo ""
echo -e "${GREEN}✓ Shared memory configured${NC}"
echo ""

# Add user to kvm group if not already
if ! groups | grep -q kvm; then
    echo -e "${YELLOW}Adding user to 'kvm' group...${NC}"
    sudo usermod -a -G kvm "$USER"
    echo -e "${YELLOW}⚠ You need to log out and log back in for group changes to take effect${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Looking Glass Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Installation Summary:"
echo "  • Looking Glass client: $(which looking-glass-client)"
echo "  • Version: $LATEST_TAG"
echo "  • Shared memory: /dev/shm/looking-glass (128MB)"
echo ""
echo "Next Steps:"
echo "  1. In VirtFlow, click '👁️ Setup Looking Glass' button"
echo "  2. Start your VM"
echo "  3. In Windows, download Looking Glass host:"
echo "     https://looking-glass.io/artifact/stable/host"
echo "  4. Install and reboot Windows"
echo "  5. Looking Glass will launch automatically!"
echo ""
echo "To test manually:"
echo "  looking-glass-client -f /dev/shm/looking-glass"
echo ""
echo -e "${YELLOW}Note: If you were added to 'kvm' group, log out and log back in${NC}"
echo ""

# Cleanup option
read -p "Remove build directory ($BUILD_DIR)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd "$HOME"
    rm -rf "$BUILD_DIR"
    echo -e "${GREEN}✓ Build directory removed${NC}"
fi

echo ""
echo -e "${GREEN}Installation script completed successfully!${NC}"