# Recent Changes

**Date:** October 24, 2025

---

## Summary

Cleaned up VirtFlow interface and documentation based on user feedback.

---

## Changes Made

### 1. ✅ Removed Annoying Viewer Popup

**Issue:** Small integrated viewer popup window was annoying and poor UX

**Fix:** 
- Disabled `IntegratedVMViewer` popup in `vm_list_widget.py`
- Looking Glass now shows in its own window only
- No more duplicate/confusing windows

**File:** `src/ui/vm_list_widget.py`

---

### 2. ✅ Added Window Borders to Looking Glass

**Issue:** Looking Glass window had no titlebar, borders, or close/minimize/maximize buttons

**Fix:**
- Added `win:borderless=no` to show window decorations
- Added `win:minimize=yes` to allow minimize
- Added `win:maximize=yes` to allow maximize
- Window now has titlebar with controls
- Can resize by dragging edges
- Can close with X button

**Files:** 
- `src/ui/integrated_vm_viewer.py`
- `test_lg.sh`

**Looking Glass now has:**
- ✓ Titlebar (can drag to move)
- ✓ Close button (X)
- ✓ Minimize button
- ✓ Maximize button
- ✓ Resizable borders

---

### 3. ✅ Consolidated Documentation

**Issue:** 17+ scattered .md files creating confusion

**Fix:**
- Created single `DOCUMENTATION.md` with all information
- Organized into sections: Quick Start, GPU Passthrough, Looking Glass, Controls, Troubleshooting, Architecture
- Deleted old .md files:
  - COMPLETE_GPU_PASSTHROUGH_SOLUTION.md
  - FINAL_TEST.md
  - FIXES_SUMMARY.md
  - GPU_PASSTHROUGH_GUIDE.md
  - INTEGRATED_VIEWER.md
  - LATEST_FIXES.md
  - LOOKING_GLASS_CONTROLS.md
  - LOOKING_GLASS_SETUP.md
  - QUICKSTART.md
  - QUICK_START.md
  - README_GPU_PASSTHROUGH.md
  - START_HERE.md
  - TEST_LOOKING_GLASS.md
  - THE_REAL_PROBLEM.md
  - TROUBLESHOOTING.md
  - URGENT_FIX_SUDO.md
  - VERIFICATION_CHECKLIST.md

**Now have:**
- ✓ `DOCUMENTATION.md` - Complete guide
- ✓ `CHANGES.md` - This file
- ✓ Clean, organized documentation

---

### 4. ✅ Cleaned Up Scripts Folder

**Issue:** Too many scripts in `/scripts/` folder

**Fix:**
- Moved old/unused scripts to `scripts_backup/`:
  - `setup_early_vfio_binding.sh`
  - `stop_desktop_bind_gpu.sh`
  - `switch_to_amd_gpu.sh`
- Kept essential scripts:
  - `setup_gpu_passthrough.sh` (being integrated)
  - `setup_sudo_permissions.sh` (being integrated)
  - `install_libvirt_hooks.sh` (being integrated)
  - `test_gpu_passthrough.py` (dev tool)
- Created `scripts/README.md` explaining status

**Scripts folder now:**
- ✓ Only essential files
- ✓ Clear documentation
- ✓ Backup of old scripts
- ✓ Integration status tracked

---

## Testing

### Test the Changes:

```bash
# Start VirtFlow
python3 src/main.py

# What to verify:
# 1. ✓ No annoying popup window appears
# 2. ✓ Looking Glass window has titlebar and borders
# 3. ✓ Can minimize/maximize/close Looking Glass
# 4. ✓ Can resize Looking Glass window
# 5. ✓ Mouse control with ScrollLock still works
```

---

## Before vs After

### Before:
```
Start VM
  ↓
Annoying popup window appears ❌
  ↓
Looking Glass window (borderless, no controls) ❌
  ↓
17+ confusing .md files ❌
  ↓
Scripts folder cluttered ❌
```

### After:
```
Start VM
  ↓
Looking Glass window with titlebar and controls ✓
  ↓
No annoying popup ✓
  ↓
Single DOCUMENTATION.md ✓
  ↓
Clean scripts folder ✓
```

---

## Files Modified

### Code Changes:
- `src/ui/vm_list_widget.py` - Disabled popup viewer
- `src/ui/integrated_vm_viewer.py` - Added window borders
- `test_lg.sh` - Added window borders

### Documentation:
- Created `DOCUMENTATION.md` - All-in-one guide
- Created `CHANGES.md` - This file
- Created `scripts/README.md` - Scripts status
- Deleted 17 old .md files

### Cleanup:
- Created `scripts_backup/` folder
- Moved 3 old scripts to backup
- Cleaned up root directory

---

## Next Steps (Future Work)

1. **Complete script integration**:
   - Finish integrating `setup_gpu_passthrough.sh` into `gpu_manager.py`
   - Integrate `install_libvirt_hooks.sh`
   - Remove scripts after integration complete

2. **Package as .deb**:
   - Create Debian package
   - Bundle all dependencies
   - Single-click installation

3. **Add features**:
   - VM creation wizard
   - ISO download/management
   - Snapshot management
   - Network configuration GUI

---

## Known Issues (Still Present)

1. **GPU restore warnings**: Harmless modprobe errors when restoring GPU → Ignore
2. **Looking Glass host crashes**: If QXL missing → Fixed by keeping QXL
3. **Mouse capture on Wayland**: Must use ScrollLock only → Documented

---

## User Experience Improvements

| Issue | Status | Notes |
|-------|--------|-------|
| Annoying popup | ✅ Fixed | Disabled completely |
| No window controls | ✅ Fixed | Added titlebar, borders, buttons |
| Too many .md files | ✅ Fixed | Consolidated to 1 file |
| Cluttered scripts | ✅ Fixed | Cleaned and organized |
| Mouse auto-capture trap | ✅ Fixed | Disabled auto-capture |
| SPICE connection | ✅ Fixed | Correct parameters |
| QXL video device | ✅ Fixed | Kept for Looking Glass |

---

## Summary

**All requested changes completed:**
1. ✅ Removed annoying viewer popup
2. ✅ Added window borders/controls to Looking Glass
3. ✅ Consolidated all .md files into one
4. ✅ Cleaned up scripts folder

**VirtFlow is now cleaner and easier to use!** 🚀
