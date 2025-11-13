# VirtFlow Documentation

**Version:** 0.1.0  
**Last Updated:** October 24, 2025

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [GPU Passthrough](#gpu-passthrough)
3. [Looking Glass Setup](#looking-glass-setup)
4. [Controls & Usage](#controls--usage)
5. [Troubleshooting](#troubleshooting)
6. [Architecture](#architecture)

---

## Quick Start

### Installation

```bash
cd /home/atharv/virtflow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Launch VirtFlow

```bash
python3 src/main.py
```

### Basic Usage

1. **Start VM**: Click "▶ Start" on your VM
2. **Looking Glass launches automatically** with window controls
3. **Control mouse**: Press ScrollLock to capture/release
4. **Stop VM**: Click "Stop" button

---

## GPU Passthrough

### Overview

VirtFlow supports NVIDIA GPU passthrough for Windows VMs with automatic GPU binding/unbinding.

### Requirements

- IOMMU enabled in BIOS
- VT-d / AMD-Vi enabled
- GPU in separate IOMMU group
- VFIO drivers installed

### How It Works

**When VM starts:**
1. Detects GPU (NVIDIA GA107)
2. Binds GPU to VFIO
3. Passes GPU to Windows VM
4. GPU available in Windows

**When VM stops:**
1. Unbinds GPU from VFIO
2. Rebinds to NVIDIA host driver
3. GPU available on Linux again

### Manual GPU Operations

**Check GPU status:**
```bash
lspci -nnk | grep -A3 VGA
```

**Bind to VFIO manually:**
```bash
# Done automatically by VirtFlow, but if needed:
sudo modprobe vfio-pci
echo "10de 2489" | sudo tee /sys/bus/pci/drivers/vfio-pci/new_id
```

---

## Looking Glass Setup

### What is Looking Glass?

Looking Glass allows you to view your VM display with GPU acceleration and near-zero latency without needing a physical monitor connected to the passthrough GPU.

### Setup Steps

1. **Install Looking Glass Client** (Linux host):
   ```bash
   # In VirtFlow GUI:
   # Click "📥 Install Looking Glass" button
   ```

2. **Setup VM Configuration**:
   ```bash
   # In VirtFlow GUI:
   # Click "👁️ Setup Looking Glass" button
   # This adds IVSHMEM and QXL to VM
   ```

3. **Install Looking Glass Host** (Windows guest):
   - Download from: https://looking-glass.io/downloads
   - Install in Windows VM
   - Should auto-start on boot

4. **Start VM**:
   - Looking Glass client launches automatically
   - Window appears with borders and controls

### Requirements

- **Shared Memory**: `/dev/shm/looking-glass` (128MB)
- **IVSHMEM Device**: Added to VM automatically
- **QXL Video**: Required for display capture
- **SPICE**: Required for keyboard/mouse input
- **Looking Glass Host**: Running in Windows VM

### Architecture

```
Windows VM:
  ↓
QXL Video Device (primary display)
  ↓
Looking Glass Host captures QXL output
  ↓
Writes to IVSHMEM shared memory (/dev/shm/looking-glass)
  ↓
Looking Glass Client (Linux) reads shared memory
  ↓
Display on Linux with GPU acceleration!

NVIDIA GPU (passthrough):
  ↓
Accelerates 3D rendering in Windows
  ↓
Output goes to QXL
  ↓
Looking Glass captures it
```

**Key Points:**
- QXL is REQUIRED - it's the "screen" Looking Glass captures
- NVIDIA GPU accelerates rendering, output goes to QXL
- No physical monitor needed on passthrough GPU
- SPICE provides keyboard/mouse input

---

## Controls & Usage

### Looking Glass Window

**Window Controls:**
- **Titlebar**: Drag to move window
- **Resize**: Drag window edges/corners
- **Minimize**: Click minimize button
- **Maximize**: Click maximize button
- **Close**: Click X button (VM keeps running)

**How It Works:** VirtFlow uses a Looking Glass configuration file to manage window settings:
1. Launches Looking Glass with config file (`-C looking_glass.conf`)
2. Config file specifies: borderless=no, fullScreen=no, size=1024x768
3. Window appears with borders, titlebar, and standard controls

The configuration file is located at `src/backend/looking_glass.conf` and is passed to Looking Glass at startup.

### Mouse Control

⚠️ **IMPORTANT: Use ScrollLock ONLY!**

| Action | Key |
|--------|-----|
| Capture mouse | Press ScrollLock |
| Release mouse | Press ScrollLock again |
| Emergency release | Ctrl+Alt+Q (quit viewer) |

**DO NOT click on window to capture!** Use ScrollLock only.

**When mouse is captured:**
- ✓ Mouse works in Windows
- ✓ Windows key opens Start menu in Windows
- ✓ All shortcuts work in Windows

**When mouse is NOT captured:**
- ✗ Mouse doesn't move in Windows
- ✗ Windows key opens Linux menu
- ✗ Shortcuts go to Linux

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| ScrollLock | Capture/release mouse |
| Ctrl+Alt+F | Toggle fullscreen |
| Ctrl+Alt+Q | Quit viewer |
| Ctrl+Alt+Del | Send to Windows (when captured) |

---

## Troubleshooting

### Looking Glass Issues

#### "The host application seems to not be running"

**Cause:** Looking Glass host not running in Windows VM

**Fix:**
1. Connect via SPICE viewer (fallback)
2. In Windows, check Task Manager for `looking-glass-host.exe`
3. If not running: Start Menu → "Looking Glass (host)"
4. Or reboot Windows (auto-starts after install)

#### Window appears but no display / black screen

**Causes:**
1. Looking Glass host not running in Windows
2. QXL video device missing
3. Shared memory permissions

**Fix:**
1. Check Looking Glass host running in Windows
2. Verify QXL exists: `virsh dumpxml VM_NAME | grep qxl`
3. Check shared memory: `ls -l /dev/shm/looking-glass`

#### Mouse doesn't work

**Cause:** Mouse not captured

**Fix:** Press ScrollLock to capture mouse

#### Mouse gets stuck / can't release

**Fix:**
1. Press ScrollLock to release
2. If that fails: Ctrl+Alt+Q to quit viewer
3. Last resort: Ctrl+Alt+F3 (TTY), login, `killall looking-glass-client`

#### "Failed to connect to spice server"

**Cause:** SPICE not configured

**Fix:**
```bash
# Check SPICE
virsh dumpxml Windows11 | grep spice

# If missing, reconfigure:
# Click "Setup Looking Glass" button again
```

---

### GPU Passthrough Issues

#### GPU not detected

**Check IOMMU:**
```bash
# Should show groups
find /sys/kernel/iommu_groups/ -type l
```

**Check GPU:**
```bash
lspci -nnk | grep -A3 VGA
```

#### GPU binding fails

**Check VFIO loaded:**
```bash
lsmod | grep vfio
```

**Reload VFIO:**
```bash
sudo modprobe vfio-pci
```

#### GPU not restored after VM stops

**Manual restore:**
```bash
# Unbind from VFIO
echo "0000:10:00.0" | sudo tee /sys/bus/pci/drivers/vfio-pci/unbind

# Bind to NVIDIA
sudo modprobe nvidia
echo "0000:10:00.0" | sudo tee /sys/bus/pci/drivers/nvidia/bind
```

---

### VM Issues

#### VM won't start

**Check:**
1. Libvirt running: `systemctl status libvirtd`
2. VM exists: `virsh list --all`
3. Logs: Check console output

#### VM starts but can't control

**Check:**
1. Looking Glass window appeared?
2. Mouse captured? (Press ScrollLock)
3. SPICE connected? (Check logs)

#### Performance issues

**Check:**
1. GPU actually passed through: Check in Windows Device Manager
2. Looking Glass host running
3. CPU pinning configured (optional optimization)

---

## Architecture

### VirtFlow Design

VirtFlow is an all-in-one integrated application for VM management with GPU passthrough and Looking Glass support.

**Key Principles:**
1. ✅ NO external bash scripts - everything in Python app
2. ✅ Integrated VM viewer using Looking Glass
3. ✅ SPICE + QXL for display without physical monitor
4. ✅ GPU passthrough works alongside SPICE
5. ✅ All functionality in GUI - no command-line needed
6. ✅ Target: .deb package with dependencies bundled

### Display Architecture

```
┌─────────────────────────────────────┐
│         Windows VM                  │
│                                     │
│  ┌─────────────┐  ┌──────────────┐ │
│  │ NVIDIA GPU  │  │ QXL Video    │ │
│  │ (Passthrough│  │ (Primary)    │ │
│  └──────┬──────┘  └──────┬───────┘ │
│         │                │         │
│         └────►Rendering───┘         │
│                  │                 │
│         ┌────────▼────────┐        │
│         │ Looking Glass   │        │
│         │ Host            │        │
│         └────────┬────────┘        │
└──────────────────┼─────────────────┘
                   │
            IVSHMEM Shared Memory
            /dev/shm/looking-glass
                   │
┌──────────────────▼─────────────────┐
│         Linux Host                 │
│                                    │
│         ┌────────────────┐         │
│         │ Looking Glass  │         │
│         │ Client         │         │
│         └────────┬───────┘         │
│                  │                 │
│         ┌────────▼────────┐        │
│         │ Your Display    │        │
│         └─────────────────┘        │
└────────────────────────────────────┘
```

**Flow:**
1. Windows uses NVIDIA GPU for 3D acceleration
2. Output rendered to QXL video device
3. Looking Glass host captures QXL output
4. Writes frames to IVSHMEM shared memory
5. Looking Glass client reads from shared memory
6. Displays on Linux with GPU acceleration
7. SPICE provides keyboard/mouse input

**Benefits:**
- No physical monitor needed on passthrough GPU
- Near-zero latency (<1ms)
- GPU-accelerated rendering on both sides
- Full keyboard/mouse control
- Resizable window with controls

### Components

**Backend:**
- `libvirt_manager.py` - Libvirt connection management
- `vm_controller.py` - VM lifecycle (start/stop/pause)
- `gpu_detector.py` - GPU detection and IOMMU scanning
- `gpu_manager.py` - GPU binding/unbinding (VFIO/NVIDIA)
- `looking_glass_manager.py` - Looking Glass setup and config
- `vm_viewer_manager.py` - Viewer launch management

**UI:**
- `main_window.py` - Main application window
- `vm_list_widget.py` - VM list and controls
- `integrated_vm_viewer.py` - Looking Glass launcher
- `gpu_config_dialog.py` - GPU configuration dialog

**Utils:**
- `logger.py` - Logging configuration
- `sudo_helper.py` - Sudo operations without password

---

## Configuration Files

### Shared Memory

**File:** `/dev/shm/looking-glass`  
**Size:** 128MB  
**Owner:** `libvirt-qemu:kvm`  
**Permissions:** `660`

**Created automatically by VirtFlow**

### VM XML

Looking Glass configuration adds:

```xml
<devices>
  <!-- IVSHMEM for Looking Glass -->
  <shmem name='looking-glass'>
    <model type='ivshmem-plain'/>
    <size unit='M'>128</size>
  </shmem>
  
  <!-- QXL for display capture -->
  <video>
    <model type='qxl' ram='65536' vram='65536' vgamem='16384' heads='1' primary='yes'/>
  </video>
  
  <!-- SPICE for input -->
  <graphics type='spice' autoport='yes' listen='127.0.0.1'>
    <listen type='address' address='127.0.0.1'/>
  </graphics>
</devices>
```

---

## Scripts (Legacy - Being Integrated)

Scripts in `/scripts/` folder are being integrated into the Python app. Keep for reference:

- `setup_gpu_passthrough.sh` - GPU setup (now in gui_manager.py)
- `setup_sudo_permissions.sh` - Sudo setup (now in sudo_helper.py)
- `install_libvirt_hooks.sh` - Hooks setup (being integrated)

**DO NOT run these scripts manually!** Use VirtFlow GUI.

---

## Development

### Requirements

- Python 3.13+
- PySide6 (Qt6 bindings)
- libvirt-python
- Looking Glass client (B7)

### Running from Source

```bash
cd /home/atharv/virtflow
source venv/bin/activate
python3 src/main.py
```

### Packaging (.deb)

**TODO:** Package as .deb with all dependencies

---

## Known Issues

1. **Wayland auto-capture issue**: Auto-capture causes mouse trap on Wayland → Fixed by disabling auto-capture
2. **GPU restore errors**: Sometimes shows modprobe errors but GPU restores successfully → Harmless warnings
3. **Looking Glass host crashes**: If QXL missing or wrong configuration → Fixed by keeping QXL

---

## FAQ

### Why do I need QXL if I have GPU passthrough?

QXL is the "screen" that Looking Glass captures. Even though NVIDIA GPU does the rendering, the output goes to QXL, which Looking Glass then streams to Linux. Without QXL, Looking Glass has nothing to capture.

### Can I use Looking Glass without GPU passthrough?

Yes! Looking Glass works with just QXL. GPU passthrough makes 3D rendering faster, but isn't required.

### Why does Looking Glass say "host not running"?

The Looking Glass host application in Windows isn't running. Start it from the Start menu or reboot Windows.

### How do I use the Windows VM without Looking Glass?

You can connect a physical monitor to the passthrough GPU, or use SPICE viewer (virt-viewer) to connect to QXL.

### What's the difference between Looking Glass and SPICE?

- **SPICE**: Remote desktop protocol, some latency, no GPU acceleration on client
- **Looking Glass**: Direct shared memory access, <1ms latency, GPU-accelerated on both sides

Looking Glass is much faster but requires setup. SPICE is the fallback.

---

## Support

**GitHub:** (TODO: Add repository URL)  
**Issues:** (TODO: Add issue tracker URL)  
**Documentation:** This file!

---

## License

(TODO: Add license)

---

## Changelog

### v0.1.0 (October 2025)

- Initial VirtFlow release
- GPU passthrough support
- Looking Glass integration
- Automatic GPU binding/unbinding
- Integrated viewer with window controls
- SPICE fallback support
