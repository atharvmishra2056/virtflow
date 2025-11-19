# The Wolf VM

The Wolf VM is a modern, graphical front-end for KVM/QEMU, built in Python and PySide6. It is designed to solve the most significant pain point for VFIO users: the reliance on complex, manual scripts for GPU passthrough.

The application provides a "Nebula" UI for managing virtual machines and a "HyperGlass" settings panel for configuring performance, all while handling driver binding (NVIDIA vs. VFIO) and XML generation automatically.



## Features

* **Python-First Backend:** No more shell scripts. All VM creation, driver management, and XML configuration is handled by a robust Python backend.
* **On-the-Fly Driver Management:** Automatically unbinds NVIDIA drivers and binds to VFIO when starting a GPU passthrough VM, and restores them on shutdown.
* **Guided Setup:** Simple, one-click installers and guides for Sudo permissions and Looking Glass.
* **Dual Display Support:** Right-click any VM to choose your display preference:
    * **SPICE:** For high-compatibility, smooth 2D work.
    * **Looking Glass:** For high-performance, low-latency gaming.
* **HyperGlass Settings:** A beautiful, translucent "real glass" settings panel (based on `xyz.html`) to manage:
    * Core Hardware (vCPUs, RAM)
    * Display Settings (VRAM, 3D Acceleration)
    * Performance (CPU Pinning, HugePages)
    * SPICE Optimizations (OpenGL vs. QXL)
    * TPM 2.0 (for Windows 11)
* **Automated Guest Tools:** Right-click a running VM to automatically install VirtIO drivers via the QEMU Guest Agent.



## Getting Started

### 1. Dependencies

The Wolf VM requires several system packages to function.

**Required Binaries:**
* `qemu-system-x86_64`
* `virsh` (from `libvirt-clients`)
* `virt-viewer` (for SPICE)
* `looking-glass-client` (for Looking Glass)
* `xdotool` & `wmctrl` (for window management)

**On Debian/Ubuntu-based systems:**
```bash
sudo apt update
sudo apt install qemu-system-x86 qemu-kvm libvirt-daemon-system libvirt-clients \
                 bridge-utils virt-manager ovmf xdotool wmctrl \
                 python3-pyside6.qtwidgets python3-pyside6.qtgui