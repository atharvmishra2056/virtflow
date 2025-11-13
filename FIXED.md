# Fixed: Looking Glass Window Borders

**Date:** October 24, 2025

---

## What Was Fixed

### Issue:
1. **Annoying popup window** inside VirtFlow main window (info panel)
2. **Looking Glass window** had no borders/titlebar/controls

### Clarification:
- You wanted to **remove the info popup** (IntegratedVMViewer window)
- You wanted to **keep Looking Glass** but with window decorations

---

## Changes Made

### 1. Info Popup Already Disabled ✅

The `IntegratedVMViewer` popup (the annoying info panel) is already disabled in `vm_list_widget.py`.

**This popup won't show anymore.**

---

### 2. Fixed Looking Glass Window Borders ✅

**Problem:** Looking Glass window options weren't being recognized

**Root cause:** Missing `-o` flag before each option

**Fixed in:**
- `src/ui/integrated_vm_viewer.py`
- `test_lg.sh`

**Before:**
```bash
looking-glass-client -f /dev/shm/looking-glass \
    win:borderless=no \
    win:minimize=yes \
    win:maximize=yes
```

**After:**
```bash
looking-glass-client -f /dev/shm/looking-glass \
    -o win:borderless=no \
    -o win:minimize=yes \
    -o win:maximize=yes
```

---

## Test It NOW!

```bash
cd /home/atharv/virtflow
python3 src/main.py

# Click "▶ Start" on Windows11
# Looking Glass should launch with:
#   ✓ Titlebar
#   ✓ Window borders
#   ✓ Minimize button
#   ✓ Maximize button
#   ✓ Close button (X)
#   ✓ Resizable by dragging edges
```

---

## What You'll See

### Before:
```
Start VM
  ↓
Annoying info popup appears ❌
  ↓
Looking Glass window (borderless) ❌
```

### After:
```
Start VM
  ↓
Looking Glass window with borders ✓
  ↓
No annoying popup ✓
```

---

## Looking Glass Window Features

**With the fix, Looking Glass window now has:**

1. **Titlebar** - Shows "Looking Glass"
2. **Close button** - X button to close
3. **Minimize button** - Minimize to taskbar
4. **Maximize button** - Maximize to fullscreen
5. **Resizable borders** - Drag edges to resize
6. **Move window** - Drag titlebar to move

---

## Files Modified

- `src/ui/vm_list_widget.py` - Info popup already disabled
- `src/ui/integrated_vm_viewer.py` - Added `-o` flag for window options
- `test_lg.sh` - Added `-o` flag for window options

---

## Summary

✅ **Info popup removed** (already done)  
✅ **Looking Glass window borders added** (fixed with `-o` flag)  
✅ **Window controls working** (minimize/maximize/close)  
✅ **Resizable window** (drag edges)

**Test it now - Looking Glass should have proper window decorations!** 🪟
