#!/usr/bin/env python3
"""
Wrapper script to launch Looking Glass with proper window decorations on Wayland.
Uses DBus to communicate with GNOME Shell to manage window properties.
"""

import subprocess
import sys
import time
import os
import signal

def get_window_id(window_name="looking-glass-client"):
    """Get the window ID using wmctrl or xdotool"""
    try:
        # Try wmctrl first
        result = subprocess.run(
            ['wmctrl', '-l'],
            capture_output=True,
            text=True,
            timeout=2
        )
        for line in result.stdout.split('\n'):
            if window_name in line:
                window_id = line.split()[0]
                return window_id
    except:
        pass
    
    # Try xdotool
    try:
        result = subprocess.run(
            ['xdotool', 'search', '--name', window_name],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.stdout.strip():
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    return None

def apply_decorations(window_id):
    """Apply window decorations using various methods"""
    if not window_id:
        return False
    
    try:
        # Try using xprop to set window properties
        subprocess.run(
            ['xprop', '-id', window_id, '-f', '_MOTIF_WM_HINTS', '32c', '-set', '_MOTIF_WM_HINTS', '0, 0, 1, 0, 0'],
            capture_output=True,
            timeout=2
        )
        return True
    except:
        pass
    
    return False

def main():
    """Main wrapper function"""
    # Get arguments (skip script name)
    lg_args = sys.argv[1:]
    
    # Launch Looking Glass
    print(f"Launching Looking Glass: {' '.join(lg_args)}")
    process = subprocess.Popen(
        lg_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    
    # Wait for window to appear
    print("Waiting for window to appear...")
    for i in range(10):  # Try for 10 seconds
        time.sleep(0.5)
        window_id = get_window_id()
        if window_id:
            print(f"Found window: {window_id}")
            if apply_decorations(window_id):
                print("Applied decorations")
            break
    
    # Keep the wrapper running until Looking Glass exits
    try:
        process.wait()
    except KeyboardInterrupt:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)

if __name__ == '__main__':
    main()
