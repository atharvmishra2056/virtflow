"""
VFIO Manager - On-demand NVIDIA loading
"""

import subprocess
import time
from pathlib import Path
from utils.logger import logger
import os # <-- NEW: Import os


class VFIOManager:
    """Manages VFIO with on-demand NVIDIA"""
    
    def __init__(self):
        self._ensure_vfio_loaded()
    
    # --- NEW: Static method to provide sudoers content ---
    @staticmethod
    def get_sudoers_content() -> str:
        # Get the current username
        username = os.getenv("SUDO_USER", os.getenv("USER", "your_user"))
        
        # This content is from your scripts/setup_sudo_permissions.sh
        content = f"""# VirtFlow GPU Passthrough - Passwordless sudo for specific operations
# Created: {time.strftime("%Y-%m-%d")}
# This file MUST be placed in /etc/sudoers.d/ and have 0440 permissions.

# Allow tee for GPU binding (used to write to sysfs)
{username} ALL=(root) NOPASSWD: /usr/bin/tee

# Allow sh for sysfs writes (more reliable than tee for driver binding)
{username} ALL=(root) NOPASSWD: /usr/bin/sh
{username} ALL=(root) NOPASSWD: /bin/sh

# Allow module operations (modprobe paths)
{username} ALL=(root) NOPASSWD: /usr/sbin/modprobe
{username} ALL=(root) NOPASSWD: /sbin/modprobe

# Allow pkill for killing GPU processes
{username} ALL=(root) NOPASSWD: /usr/bin/pkill

# Allow reading dmesg
{username} ALL=(root) NOPASSWD: /usr/bin/dmesg
"""
        return content
    
    def _ensure_vfio_loaded(self):
        """Load VFIO modules"""
        subprocess.run(['sudo', 'modprobe', 'vfio'], check=False, capture_output=True)
        subprocess.run(['sudo', 'modprobe', 'vfio_pci'], check=False, capture_output=True)
        subprocess.run(['sudo', 'modprobe', 'vfio_iommu_type1'], check=False, capture_output=True)
    
    def _sysfs_write(self, path: str, value: str) -> bool:
        """Write to sysfs"""
        try:
            cmd = f'echo "{value}" > {path}'
            result = subprocess.run(['sudo', 'sh', '-c', cmd], capture_output=True, timeout=3, text=True)
            if result.returncode != 0 and result.stderr:
                logger.debug(f"sysfs_write to {path} failed: {result.stderr}")
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"sysfs_write exception: {e}")
            return False

    # --- TASK 1.2: Logic Merged from gpu_worker.py ---
    def _remove_nvidia_driver(self):
        """Remove NVIDIA driver modules to free GPU"""
        try:
            logger.info("Removing NVIDIA driver modules...")
            
            # Stop any processes using NVIDIA
            subprocess.run(['sudo', 'pkill', '-9', '-f', 'nvidia'], timeout=10, capture_output=True)
            time.sleep(0.5)
            
            # Remove audio driver first (snd_hda_intel)
            logger.info("Removing audio driver...")
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
                        logger.info(f"Removed {module}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Timeout removing {module}")
                except Exception:
                    pass
            
            time.sleep(1)
            logger.info("NVIDIA driver removed")
            return True
            
        except Exception as e:
            logger.warning(f"Warning: Could not fully remove NVIDIA driver: {e}")
            return True  # Continue anyway
            
    def _load_nvidia_driver(self):
        """Reload NVIDIA driver modules"""
        try:
            logger.info("Loading NVIDIA driver...")
            subprocess.run(['sudo', 'modprobe', 'nvidia'], check=False, timeout=5)
            subprocess.run(['sudo', 'modprobe', 'nvidia_modeset'], check=False, timeout=5)
            subprocess.run(['sudo', 'modprobe', 'nvidia_drm'], check=False, timeout=5)
            subprocess.run(['sudo', 'modprobe', 'nvidia_uvm'], check=False, timeout=5)
            
            # Reload audio driver
            logger.info("Loading audio driver...")
            subprocess.run(['sudo', 'modprobe', 'snd_hda_intel'], check=False, timeout=5)
            
            time.sleep(1) # Give modules time to settle
            
            logger.info("NVIDIA driver loaded")
            return True
        except Exception as e:
            logger.warning(f"Warning: Could not reload NVIDIA driver: {e}")
            return False
    # --- END TASK 1.2 MERGE ---
    
    def bind_gpu_to_vfio(self, gpu) -> bool:
        """
        Bind GPU to VFIO
        """
        logger.info(f"Binding {gpu.full_name} to VFIO...")
        
        try:
            # --- TASK 1.2 MODIFICATION ---
            # Call internal method to remove NVIDIA driver first
            self._remove_nvidia_driver()
            # --- END MODIFICATION ---
            
            for device in gpu.all_devices:
                logger.info(f"Binding {device.address} to vfio-pci...")
                
                # First, unbind from current driver if any
                driver_path = Path(f"/sys/bus/pci/devices/{device.address}/driver")
                if driver_path.exists():
                    unbind_path = f"{driver_path}/unbind"
                    logger.debug(f"Unbinding {device.address} from current driver")
                    self._sysfs_write(unbind_path, device.address)
                    time.sleep(0.2)
                
                # Set driver override
                override_path = f"/sys/bus/pci/devices/{device.address}/driver_override"
                self._sysfs_write(override_path, "vfio-pci")
                
                # Register device ID with vfio-pci
                new_id = f"/sys/bus/pci/drivers/vfio-pci/new_id"
                self._sysfs_write(new_id, f"{device.vendor_id} {device.device_id}")
                
                time.sleep(0.3)
                
                # Probe device
                probe = "/sys/bus/pci/drivers_probe"
                if self._sysfs_write(probe, device.address):
                    logger.info(f"✓ Bound {device.address} to vfio-pci")
                else:
                    # Fallback: direct bind
                    bind = "/sys/bus/pci/drivers/vfio-pci/bind"
                    if self._sysfs_write(bind, device.address):
                        logger.info(f"✓ Bound {device.address} to vfio-pci (fallback)")
                    else:
                        logger.error(f"Failed to bind {device.address}")
                        return False
            
            # Verify
            short_addr = gpu.pci_address.split(':', 1)[1]
            result = subprocess.run(
                ['lspci', '-k', '-s', short_addr],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'vfio-pci' in result.stdout:
                logger.info(f"✓✓✓ {gpu.full_name} bound to vfio-pci!")
                return True
            else:
                logger.error(f"Binding verification failed:\n{result.stdout}")
                return False
            
        except Exception as e:
            logger.exception(f"Failed to bind GPU: {e}")
            return False
    
    def unbind_gpu_from_vfio(self, gpu) -> bool:
        """
        Unbind GPU and load NVIDIA for host use
        """
        logger.info(f"Unbinding {gpu.full_name} from VFIO...")
        
        try:
            # Unbind from vfio-pci
            for device in gpu.all_devices:
                # Unbind
                driver_path = Path(f"/sys/bus/pci/devices/{device.address}/driver")
                if driver_path.exists():
                    unbind = f"{driver_path}/unbind"
                    self._sysfs_write(unbind, device.address)
                
                # Clear override
                override = f"/sys/bus/pci/devices/{device.address}/driver_override"
                self._sysfs_write(override, "")
            
            # --- TASK 1.2 MODIFICATION ---
            # NOW load NVIDIA modules for host use
            logger.info("Loading NVIDIA modules for host...")
            self._load_nvidia_driver()
            # --- END MODIFICATION ---
            
            time.sleep(2)
            
            # Bind to nvidia driver
            for device in gpu.all_devices:
                bind = "/sys/bus/pci/drivers/nvidia/bind"
                self._sysfs_write(bind, device.address)
            
            logger.info(f"✓ {gpu.full_name} restored to host with NVIDIA driver")
            logger.info("You can now use: nvidia-smi")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to unbind: {e}")
            return False