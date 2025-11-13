# FINAL FIX: Looking Glass Auto-Launch

**Date:** October 24, 2025  
**Issue:** Looking Glass still not launching automatically

---

## The Real Problem

There were TWO issues:

### Issue 1: vm_viewer_manager didn't know about Looking Glass ✅ FIXED
- Added Looking Glass detection
- Added Looking Glass launch method

### Issue 2: vm_list_widget wasn't calling vm_viewer_manager ❌ THIS WAS THE BLOCKER!

**The `_launch_viewer()` method was returning immediately without doing anything!**

```python
def _launch_viewer(self, vm_name: str):
    logger.info(f"VM viewer launch skipped for '{vm_name}'")
    return  # ← EXITS HERE! Never calls vm_viewer_manager!
```

**This is why you saw:**
```
INFO: VM viewer launch skipped for 'Windows11' - Looking Glass handles display
```

And nothing launched!

---

## The Complete Fix

### File 1: `src/backend/vm_viewer_manager.py` ✅
- Added `_check_looking_glass_configured()` - Detects IVSHMEM
- Added `_launch_looking_glass()` - Launches Looking Glass
- Modified `launch_viewer()` - Checks for Looking Glass first

### File 2: `src/ui/vm_list_widget.py` ✅ CRITICAL FIX
**Before (BROKEN):**
```python
def _launch_viewer(self, vm_name: str):
    logger.info(f"VM viewer launch skipped...")
    return  # ← Exits immediately!
```

**After (FIXED):**
```python
def _launch_viewer(self, vm_name: str):
    # Get domain object
    domain = self.controller.manager.get_domain(vm_name)
    
    # Call vm_viewer_manager to launch viewer
    success = self.controller.viewer_manager.launch_viewer(
        vm_name=vm_name,
        domain=domain,
        wait_for_vm=True,
        fullscreen=False
    )
```

---

## The Complete Flow (Fixed)

```
1. User clicks "▶ Start" in VirtFlow
   ↓
2. VM starts successfully
   ↓
3. _launch_viewer(vm_name) called
   ↓
4. Gets domain object
   ↓
5. Calls controller.viewer_manager.launch_viewer()
   ↓
6. vm_viewer_manager checks: Does VM have Looking Glass?
   ↓
7. YES: Calls _launch_looking_glass()
   ↓
8. Gets SPICE connection info
   ↓
9. Launches: looking-glass-client -f /dev/shm/looking-glass spice:host=127.0.0.1 spice:port=5900
   ↓
10. Looking Glass window appears! ✓
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

## What You Should See

### In the logs:
```
INFO: Starting VM 'Windows11'...
INFO: VM 'Windows11' started successfully
INFO: VM has Looking Glass configured
INFO: VM has Looking Glass, launching Looking Glass client...
INFO: Launching Looking Glass client...
INFO: SPICE URI: spice://127.0.0.1:5900
INFO: Using SPICE: host=127.0.0.1, port=5900
INFO: Launching: looking-glass-client -f /dev/shm/looking-glass -p 0 spice:host=127.0.0.1 spice:port=5900
INFO: Looking Glass launched successfully for 'Windows11'
INFO: Launched viewer for 'Windows11'
```

### On your screen:
- Looking Glass window appears
- Shows Windows desktop
- Has window decorations (titlebar, close button)
- Press ScrollLock to capture mouse

---

## Files Modified

1. `src/backend/vm_viewer_manager.py` - Added Looking Glass detection and launch
2. `src/ui/vm_list_widget.py` - Fixed to actually call vm_viewer_manager

---

## Summary

| Issue | Cause | Fix | Status |
|-------|-------|-----|--------|
| Looking Glass not launching | vm_list_widget returning early | Call vm_viewer_manager properly | ✅ Fixed |
| No Looking Glass detection | vm_viewer_manager didn't check | Added detection logic | ✅ Fixed |
| No Looking Glass launch | No launch method | Added _launch_looking_glass() | ✅ Fixed |

---

## Why It Didn't Work Before

**The chain was broken at step 3:**

```
Start VM → _launch_viewer() → RETURN (exit) ❌
                                ↓
                          Never reached vm_viewer_manager!
```

**Now it works:**

```
Start VM → _launch_viewer() → vm_viewer_manager.launch_viewer() ✓
                                ↓
                          Detects Looking Glass ✓
                                ↓
                          Launches Looking Glass ✓
```

---

## Test Results Expected

**When you start the VM:**
1. ✅ VM starts
2. ✅ Looking Glass window appears automatically
3. ✅ Window has titlebar and controls
4. ✅ Shows Windows desktop
5. ✅ Press ScrollLock to capture mouse
6. ✅ Everything works!

**No more manual `./test_lg.sh` needed!** 🚀

---

## If It Still Doesn't Work

Check the logs for:
```
INFO: VM has Looking Glass configured
INFO: Launching Looking Glass client...
```

If you don't see these lines, the detection might be failing. Let me know!
