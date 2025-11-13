#!/usr/bin/env python3
"""
GPU Worker - Isolated subprocess for GPU binding operations
WITH NVIDIA DRIVER REMOVAL
"""

import sys
import time
import subprocess
import os
from pathlib import Path


def log(message):
    """Print to stdout for parent process"""
    print(f"[GPU_WORKER] {message}", flush=True)


def ensure_vfio_loaded():
    """Ensure VFIO modules are loaded before binding"""
    try:
        modules = ['vfio', 'vfio_iommu_type1', 'vfio_pci']
        for module in modules:
            subprocess.run(['sudo', 'modprobe', module], timeout=5, capture_output=True)
        time.sleep(1)
        log("VFIO modules loaded")
        return True
    except Exception as e:
        log(f"ERROR loading VFIO modules: {e}")
        return False


def remove_nvidia_driver():
    """Remove NVIDIA driver modules to free GPU"""
    try:
        log("Removing NVIDIA driver modules...")
        
        # Stop any processes using NVIDIA
        subprocess.run(['sudo', 'pkill', '-9', '-f', 'nvidia'], timeout=10, capture_output=True)
        time.sleep(0.5)
        
        # Remove audio driver first (snd_hda_intel)
        log("Removing audio driver...")
        subprocess.run(['sudo', 'modprobe', '-r', 'snd_hda_intel'], timeout=10, capture_output=True)
        time.sleep(0.3)
        
        # Remove modules in reverse dependency order
        nvidia_modules = [
            'nvidia_uvm',
            'nvidia_drm', 
            'nvidia_modeset',
            'nvidia'
        ]
        
        for module in nvidia_modules:
            try:
                result = subprocess.run(
                    ['sudo', 'modprobe', '-r', module],
                    timeout=10,
                    capture_output=True
                )
                if result.returncode == 0:
                    log(f"Removed {module}")
            except subprocess.TimeoutExpired:
                log(f"Timeout removing {module}")
            except Exception:
                pass
        
        time.sleep(1)
        log("NVIDIA driver removed")
        return True
        
    except Exception as e:
        log(f"Warning: Could not fully remove NVIDIA driver: {e}")
        return True  # Continue anyway


def load_nvidia_driver():
    """Reload NVIDIA driver modules"""
    try:
        log("Loading NVIDIA driver...")
        subprocess.run(['sudo', 'modprobe', 'nvidia'], timeout=5, capture_output=True)
        time.sleep(1)
        
        # Reload audio driver
        log("Loading audio driver...")
        subprocess.run(['sudo', 'modprobe', 'snd_hda_intel'], timeout=5, capture_output=True)
        time.sleep(0.5)
        
        log("NVIDIA driver loaded")
        return True
    except Exception as e:
        log(f"Warning: Could not reload NVIDIA driver: {e}")
        return False


def unbind_device(pci_address):
    """Unbind device from current driver"""
    try:
        driver_path = Path(f"/sys/bus/pci/devices/{pci_address}/driver")
        
        if not driver_path.exists():
            log(f"Device {pci_address} has no driver bound")
            return True
        
        unbind_path = driver_path / "unbind"
        
        # Direct write (fastest method)
        result = subprocess.run(
            ['sudo', 'sh', '-c', f'echo "{pci_address}" > {unbind_path}'],
            timeout=3,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            log(f"Unbound {pci_address}")
            time.sleep(0.3)
            return True
        else:
            log(f"Could not unbind {pci_address} (may already be free)")
            return True  # Continue anyway
                
    except Exception as e:
        log(f"Warning unbinding {pci_address}: {e}")
        return True  # Continue anyway


def bind_to_vfio(pci_address, vendor_id, device_id):
    """Bind device to vfio-pci"""
    try:
        # Check if device exists
        device_path = f"/sys/bus/pci/devices/{pci_address}"
        if not os.path.exists(device_path):
            log(f"ERROR: Device path {device_path} does not exist")
            return False
        
        # Method 1: Try driver_override (preferred)
        override_path = f"{device_path}/driver_override"
        if os.path.exists(override_path):
            log(f"Using driver_override method for {pci_address}")
            
            # Set override using sh -c (avoids tee hanging)
            result = subprocess.run(
                ['sudo', 'sh', '-c', f'echo "vfio-pci" > {override_path}'],
                timeout=3,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                log(f"Warning: driver_override failed: {result.stderr}")
            else:
                time.sleep(0.2)
                
                # Probe device
                probe_path = "/sys/bus/pci/drivers_probe"
                result = subprocess.run(
                    ['sudo', 'sh', '-c', f'echo "{pci_address}" > {probe_path}'],
                    timeout=3,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Verify binding
                    time.sleep(0.3)
                    driver_path = f"{device_path}/driver"
                    if os.path.exists(driver_path):
                        driver = os.path.basename(os.readlink(driver_path))
                        if driver == "vfio-pci":
                            log(f"SUCCESS: {pci_address} bound to vfio-pci")
                            return True
        
        # Method 2: Try new_id + bind (fallback)
        log(f"Trying new_id method for {pci_address}")
        
        # Register device ID
        new_id_path = "/sys/bus/pci/drivers/vfio-pci/new_id"
        result = subprocess.run(
            ['sudo', 'sh', '-c', f'echo "{vendor_id} {device_id}" > {new_id_path}'],
            timeout=3,
            capture_output=True,
            text=True
        )
        time.sleep(0.2)
        
        # Direct bind
        bind_path = "/sys/bus/pci/drivers/vfio-pci/bind"
        result = subprocess.run(
            ['sudo', 'sh', '-c', f'echo "{pci_address}" > {bind_path}'],
            timeout=3,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            time.sleep(0.3)
            # Verify
            driver_path = f"{device_path}/driver"
            if os.path.exists(driver_path):
                driver = os.path.basename(os.readlink(driver_path))
                if driver == "vfio-pci":
                    log(f"SUCCESS: {pci_address} bound to vfio-pci via new_id")
                    return True
        
        log(f"ERROR: Failed to bind {pci_address} to vfio-pci")
        log(f"  Device path exists: {os.path.exists(device_path)}")
        log(f"  Override path exists: {os.path.exists(override_path)}")
        
        # Show current driver
        driver_path = f"{device_path}/driver"
        if os.path.exists(driver_path):
            try:
                current_driver = os.path.basename(os.readlink(driver_path))
                log(f"  Current driver: {current_driver}")
            except:
                pass
        else:
            log(f"  No driver currently bound")
        
        return False
                
    except subprocess.TimeoutExpired as e:
        log(f"TIMEOUT binding {pci_address}: Operation took too long")
        log(f"  This usually means sudo requires password")
        log(f"  Add gpu_worker.py to sudoers or run setup script")
        return False
    except Exception as e:
        log(f"ERROR binding {pci_address}: {e}")
        import traceback
        log(traceback.format_exc())
        return False


def bind_to_driver(pci_address, driver_name):
    """Bind device to specific driver"""
    try:
        bind_path = f"/sys/bus/pci/drivers/{driver_name}/bind"
        result = subprocess.run(
            ['sudo', 'sh', '-c', f'echo "{pci_address}" > {bind_path}'],
            timeout=3,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            log(f"Bound {pci_address} to {driver_name}")
            return True
        else:
            log(f"Could not bind {pci_address} to {driver_name}: {result.stderr}")
            return False
                
    except Exception as e:
        log(f"Error binding {pci_address}: {e}")
        return False


def bind_gpu_to_vfio(devices):
    """Bind all GPU devices to VFIO"""
    log(f"Starting VFIO bind for {len(devices)} devices")
    
    # CRITICAL: Remove NVIDIA driver first!
    remove_nvidia_driver()
    
    for device in devices:
        pci_addr = device['address']
        vendor_id = device['vendor_id']
        device_id = device['device_id']
        
        log(f"Processing {pci_addr}...")
        
        # Unbind
        unbind_device(pci_addr)
        
        # Bind to VFIO
        if not bind_to_vfio(pci_addr, vendor_id, device_id):
            log(f"ERROR: Failed to bind {pci_addr} to VFIO")
            return False
        
        time.sleep(0.3)
    
    log("All devices bound to VFIO successfully")
    return True


def unbind_gpu_from_vfio(devices, driver_name):
    """Unbind all GPU devices from VFIO and restore to host driver"""
    log(f"Starting VFIO unbind for {len(devices)} devices")
    
    for device in devices:
        pci_addr = device['address']
        
        log(f"Processing {pci_addr}...")
        
        # Clear driver override
        override_path = f"/sys/bus/pci/devices/{pci_addr}/driver_override"
        subprocess.run(
            ['sudo', 'sh', '-c', f'echo "" > {override_path}'],
            timeout=3,
            capture_output=True,
            text=True
        )
        
        # Unbind from VFIO
        unbind_device(pci_addr)
        
        # Bind to host driver
        bind_to_driver(pci_addr, driver_name)
        
        time.sleep(0.3)
    
    # Reload NVIDIA driver
    if driver_name == "nvidia":
        load_nvidia_driver()
    
    log(f"All devices restored to {driver_name}")
    return True


def main():
    """Main worker entry point"""
    if len(sys.argv) < 2:
        print("ERROR: No operation specified", file=sys.stderr)
        sys.exit(1)
    
    # Load VFIO modules
    if not ensure_vfio_loaded():
        print("ERROR: Could not load VFIO modules", file=sys.stderr)
        sys.exit(1)
    
    operation = sys.argv[1]
    
    try:
        if operation == "bind":
            devices = []
            for arg in sys.argv[2:]:
                parts = arg.split('|')
                if len(parts) == 3:
                    devices.append({
                        'address': parts[0],
                        'vendor_id': parts[1],
                        'device_id': parts[2]
                    })
            
            if not devices:
                print("ERROR: No devices specified", file=sys.stderr)
                sys.exit(1)
            
            success = bind_gpu_to_vfio(devices)
            sys.exit(0 if success else 1)
            
        elif operation == "unbind":
            if len(sys.argv) < 3:
                print("ERROR: No driver name specified", file=sys.stderr)
                sys.exit(1)
            
            driver_name = sys.argv[2]
            devices = [{'address': addr} for addr in sys.argv[3:]]
            
            if not devices:
                print("ERROR: No devices specified", file=sys.stderr)
                sys.exit(1)
            
            success = unbind_gpu_from_vfio(devices, driver_name)
            sys.exit(0 if success else 1)
            
        else:
            print(f"ERROR: Unknown operation '{operation}'", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
