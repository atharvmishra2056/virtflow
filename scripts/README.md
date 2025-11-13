# Scripts Directory

**Note:** These scripts are legacy and being integrated into the VirtFlow Python application.

**DO NOT run these manually!** Use the VirtFlow GUI instead.

---

## Current Scripts

### `setup_gpu_passthrough.sh`
- **Status:** Being integrated into `gpu_manager.py`
- **Purpose:** Configure GPU passthrough with VFIO
- **Use:** VirtFlow GUI handles this automatically

### `setup_sudo_permissions.sh`
- **Status:** Being integrated into `sudo_helper.py`
- **Purpose:** Configure passwordless sudo for libvirt operations
- **Use:** VirtFlow GUI handles this automatically

### `install_libvirt_hooks.sh`
- **Status:** Being integrated
- **Purpose:** Install libvirt hooks for GPU binding/unbinding
- **Use:** Will be integrated into VirtFlow

### `test_gpu_passthrough.py`
- **Status:** Development/testing tool
- **Purpose:** Test GPU passthrough functionality
- **Use:** For development only

---

## Backup Scripts

Moved to `/scripts_backup/`:
- `setup_early_vfio_binding.sh` - Early VFIO binding (alternative approach)
- `stop_desktop_bind_gpu.sh` - Desktop manager GPU binding
- `switch_to_amd_gpu.sh` - Switch to AMD GPU

These are kept for reference but not needed for normal operation.

---

## Integration Status

| Script | Status | Integration Location |
|--------|--------|---------------------|
| setup_gpu_passthrough.sh | 🔄 Integrating | `gpu_manager.py` |
| setup_sudo_permissions.sh | ✅ Integrated | `sudo_helper.py` |
| install_libvirt_hooks.sh | 🔄 Integrating | TBD |
| test_gpu_passthrough.py | ⚠️ Dev tool | N/A |

---

## Usage

**Instead of running scripts, use VirtFlow GUI:**

1. Launch VirtFlow: `python3 src/main.py`
2. GPU setup happens automatically
3. All operations available through GUI

**For development:**
- Use `test_gpu_passthrough.py` to test GPU operations
- Check logs in VirtFlow GUI for debugging
