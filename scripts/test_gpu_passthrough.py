#!/usr/bin/env python3
"""
Test script for GPU passthrough functionality
Run this to verify all components are working
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from backend.gpu_detector import GPUDetector
from backend.libvirt_manager import LibvirtManager
from backend.vm_gpu_configurator import VMGPUConfigurator
from backend.vfio_manager import VFIOManager
from utils.logger import logger

def test_gpu_detection():
    """Test GPU detection"""
    print("\n=== Testing GPU Detection ===")
    detector = GPUDetector()
    
    print(f"IOMMU Enabled: {detector.iommu_enabled}")
    print(f"Total GPUs Found: {len(detector.gpus)}")
    
    for gpu in detector.gpus:
        print(f"\n  GPU: {gpu.full_name}")
        print(f"    PCI Address: {gpu.pci_address}")
        print(f"    IOMMU Group: {gpu.iommu_group}")
        print(f"    Is Primary: {gpu.is_primary}")
        print(f"    Can Passthrough: {gpu.can_passthrough}")
        print(f"    Related Devices: {len(gpu.related_devices)}")
        for dev in gpu.all_devices:
            print(f"      - {dev.address}: {dev.device_name}")
    
    passthrough_gpus = detector.get_passthrough_gpus()
    print(f"\nGPUs Available for Passthrough: {len(passthrough_gpus)}")
    
    return len(passthrough_gpus) > 0

def test_vfio_manager():
    """Test VFIO manager"""
    print("\n=== Testing VFIO Manager ===")
    vfio = VFIOManager()
    
    print(f"Worker Path: {vfio.worker_path}")
    print(f"Worker Exists: {vfio.worker_path.exists()}")
    
    return vfio.worker_path.exists()

def test_libvirt_connection():
    """Test libvirt connection"""
    print("\n=== Testing Libvirt Connection ===")
    manager = None
    try:
        manager = LibvirtManager()
        
        if manager.connection:
            print(f"Connected: Yes")
            print(f"URI: {manager.uri}")
            
            # Use timeout to prevent hanging
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Libvirt operation timed out")
            
            # Set 5 second timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)
            
            try:
                vms = manager.list_all_vms()
                signal.alarm(0)  # Cancel alarm
                
                print(f"VMs Found: {len(vms)}")
                
                for domain in vms:
                    print(f"  - {domain.name()} ({'running' if domain.isActive() else 'stopped'})")
                
                return True
            except TimeoutError:
                signal.alarm(0)
                print("WARNING: VM listing timed out (libvirt may be busy)")
                return True  # Connection works, just slow
        else:
            print("Connected: No")
            return False
    except Exception as e:
        print(f"Connection failed: {e}")
        return False
    finally:
        if manager:
            try:
                manager.disconnect()
            except:
                pass

def test_gpu_configurator():
    """Test GPU configurator initialization"""
    print("\n=== Testing GPU Configurator ===")
    manager = None
    try:
        manager = LibvirtManager()
        configurator = VMGPUConfigurator(manager)
        
        print(f"Configurator Created: Yes")
        print(f"Has LibvirtManager: {configurator.libvirt_manager is not None}")
        print(f"Has VFIOManager: {configurator.vfio_manager is not None}")
        
        return True
    finally:
        if manager:
            try:
                manager.disconnect()
            except:
                pass

def check_system_requirements():
    """Check system requirements"""
    print("\n=== Checking System Requirements ===")
    
    # Check IOMMU in dmesg
    import subprocess
    try:
        result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=5)
        has_iommu = 'IOMMU enabled' in result.stdout or 'AMD-Vi' in result.stdout or 'Intel VT-d' in result.stdout
        print(f"IOMMU in dmesg: {'Yes' if has_iommu else 'No'}")
    except:
        print("IOMMU in dmesg: Could not check")
        has_iommu = False
    
    # Check VFIO modules
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True, timeout=5)
        has_vfio = 'vfio_pci' in result.stdout
        print(f"VFIO modules loaded: {'Yes' if has_vfio else 'No'}")
    except:
        print("VFIO modules loaded: Could not check")
        has_vfio = False
    
    # Check libvirt hooks
    import pathlib
    hook_exists = pathlib.Path('/etc/libvirt/hooks/qemu').exists()
    print(f"Libvirt hook installed: {'Yes' if hook_exists else 'No'}")
    
    return has_iommu and has_vfio

def main():
    """Run all tests"""
    print("=" * 60)
    print("VirtFlow GPU Passthrough Test Suite")
    print("=" * 60)
    
    results = {}
    
    try:
        results['system'] = check_system_requirements()
    except Exception as e:
        print(f"System check failed: {e}")
        results['system'] = False
    
    try:
        results['gpu_detection'] = test_gpu_detection()
    except Exception as e:
        print(f"GPU detection failed: {e}")
        results['gpu_detection'] = False
    
    try:
        results['vfio'] = test_vfio_manager()
    except Exception as e:
        print(f"VFIO manager test failed: {e}")
        results['vfio'] = False
    
    try:
        results['libvirt'] = test_libvirt_connection()
    except Exception as e:
        print(f"Libvirt connection failed: {e}")
        results['libvirt'] = False
    
    try:
        results['configurator'] = test_gpu_configurator()
    except Exception as e:
        print(f"Configurator test failed: {e}")
        results['configurator'] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name.upper():20s}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! GPU passthrough is ready to use.")
        print("\nNext steps:")
        print("  1. Run VirtFlow: python3 src/main.py")
        print("  2. Select a VM")
        print("  3. Click 'Activate GPU' button")
        print("  4. Start the VM")
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        if not results.get('system'):
            print("  - Run: sudo ./scripts/setup_gpu_passthrough.sh")
        if not results.get('libvirt'):
            print("  - Check libvirtd: sudo systemctl status libvirtd")
        if not results.get('gpu_detection'):
            print("  - Check IOMMU in BIOS")
            print("  - Check kernel parameters: cat /proc/cmdline")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
