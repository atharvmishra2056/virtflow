"""
Global configuration and constants for VirtFlow
"""

import os
from pathlib import Path

# Application metadata
APP_NAME = "VirtFlow"
APP_VERSION = "0.1.0"
APP_AUTHOR = "Your Name"
APP_DESCRIPTION = "Modern GPU Passthrough VM Manager"

# Paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "ui" / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
STYLES_DIR = BASE_DIR / "ui" / "styles"

# libvirt defaults
DEFAULT_LIBVIRT_URI = "qemu:///system"
VM_STORAGE_POOL = "default"
DEFAULT_VM_RAM = 4096  # MB
DEFAULT_VM_VCPUS = 2
DEFAULT_VM_DISK_SIZE = 40  # GB

# GPU Passthrough
VFIO_DRIVER = "vfio-pci"
IOMMU_GROUPS_PATH = "/sys/kernel/iommu_groups"

# UI Settings
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
DEFAULT_THEME = "dark"  # "dark" or "light"
ENABLE_ANIMATIONS = True
ANIMATION_DURATION = 300  # ms

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = Path.home() / ".local" / "share" / "virtflow" / "virtflow.log"

# Ensure log directory exists
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# GPU Detection
GPU_VENDOR_NVIDIA = "10de"
GPU_VENDOR_AMD = "1002"
GPU_VENDOR_INTEL = "8086"