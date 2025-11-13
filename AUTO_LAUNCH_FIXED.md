# Fixed: Looking Glass Auto-Launch

**Date:** October 24, 2025

---

## Problem

Looking Glass was NOT launching automatically when starting VM from VirtFlow. You had to manually run `./test_lg.sh` to launch it.

---

## Root Cause

The `vm_viewer_manager.py` was only launching `virt-viewer` (SPICE viewer), not Looking Glass!

**The flow was:**
```
Start VM
  ↓
vm_viewer_manager.launch_viewer()
  ↓
Launches virt-viewer (SPICE) ❌
  ↓
Looking Glass never launches ❌
```

---

## The Fix

### Modified: `src/backend/vm_viewer_manager.py`

**Added:**
1. `_check_looking_glass_configured()` - Detects if VM has IVSHMEM device
2. `_launch_looking_glass()` - Launches Looking Glass client with SPICE connection
3. Modified `launch_viewer()` - Checks for Looking Glass first, then falls back to virt-viewer

**New flow:**
```
Start VM
  ↓
vm_viewer_manager.launch_viewer()
  ↓
Check if VM has Looking Glass (IVSHMEM device)
  ↓
YES: Launch Looking Glass client ✓
NO: Launch virt-viewer (SPICE)
```

---

## What Changed

### Before (Broken):
```python
def launch_viewer(...):
    # Always launched virt-viewer
    cmd = ['virt-viewer', '--connect', 'qemu:///system', vm_name]
    subprocess.Popen(cmd)
```

### After (Fixed):
```python
def launch_viewer(...):
    # Check for Looking Glass first
    if self._check_looking_glass_configured(domain):
        return self._launch_looking_glass(vm_name, domain)
    
    # Fallback to virt-viewer
    cmd = ['virt-viewer', '--connect', 'qemu:///system', vm_name]
    subprocess.Popen(cmd)
```

---

## Looking Glass Launch Details

**The `_launch_looking_glass()` method:**

1. Checks if `looking-glass-client` is installed
2. Gets SPICE connection info from `virsh domdisplay`
3. Parses SPICE host and port
4. Launches Looking Glass with:
   - Shared memory: `/dev/shm/looking-glass`
   - SPICE connection for keyboard/mouse
   - Manual mouse capture (ScrollLock)
5. Runs as detached process

**Command executed:**
```bash
looking-glass-client \
    -f /dev/shm/looking-glass \
    -p 0 \
    spice:host=127.0.0.1 \
    spice:port=5900
```

---

## Test It NOW!

```bash
cd /home/atharv/virtflow
python3 src/main.py

# Click "▶ Start" on Windows11
# Looking Glass should launch automatically!
```

---

## What You'll See

### Before (Broken):
```
Click "▶ Start"
  ↓
VM starts
  ↓
Nothing happens ❌
  ↓
Have to manually run ./test_lg.sh ❌
```

### After (Fixed):
```
Click "▶ Start"
  ↓
VM starts
  ↓
Looking Glass launches automatically ✓
  ↓
Window appears with VM display ✓
```

---

## Detection Logic

**How it detects Looking Glass:**

```python
def _check_looking_glass_configured(domain):
    # Parse VM XML
    xml = domain.XMLDesc(0)
    
    # Look for IVSHMEM device named 'looking-glass'
    for shmem in xml.findall('.//devices/shmem'):
        if shmem.get('name') == 'looking-glass':
            return True  # Looking Glass configured!
    
    return False  # No Looking Glass, use virt-viewer
```

**If VM has:**
- ✅ IVSHMEM device named 'looking-glass' → Launch Looking Glass
- ❌ No IVSHMEM device → Launch virt-viewer (SPICE)

---

## Window Borders Note

The `-o` flag for window borders doesn't work (Looking Glass ignores it). The window will use default Wayland/X11 decorations, which should include:
- Titlebar
- Close button
- Minimize/Maximize (depends on window manager)

**This is normal!** Looking Glass uses the system window manager's decorations.

---

## Files Modified

- `src/backend/vm_viewer_manager.py` - Added Looking Glass detection and launch

---

## Summary

| Issue | Status | Fix |
|-------|--------|-----|
| Looking Glass doesn't auto-launch | ✅ Fixed | Added detection and launch logic |
| Have to manually run script | ✅ Fixed | Integrated into vm_viewer_manager |
| No window borders | ⚠️ System default | Uses window manager decorations |

---

## Next Steps

1. **Test**: Start VM from VirtFlow
2. **Verify**: Looking Glass launches automatically
3. **Use**: Press ScrollLock to capture mouse

**Looking Glass should now launch automatically when you start the VM!** 🚀
