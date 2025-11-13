"""
VM operations controller (start, stop, pause, etc.)
"""

import libvirt
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict
from backend.libvirt_manager import LibvirtManager
from backend.vm_viewer_manager import VMViewerManager
from utils.logger import logger


class VMState:
    """VM state constants"""
    NOSTATE = 0
    RUNNING = 1
    BLOCKED = 2
    PAUSED = 3
    SHUTDOWN = 4
    SHUTOFF = 5
    CRASHED = 6
    PMSUSPENDED = 7
    
    STATE_NAMES = {
        0: "No State",
        1: "Running",
        2: "Blocked",
        3: "Paused",
        4: "Shutting Down",
        5: "Shut Off",
        6: "Crashed",
        7: "Suspended"
    }


class VMController:
    """Controller for VM lifecycle operations"""
    
    def __init__(self, manager: LibvirtManager):
        """
        Initialize VM controller
        
        Args:
            manager: LibvirtManager instance
        """
        self.manager = manager
        self.viewer_manager = VMViewerManager()
    
    def get_vm_info(self, domain: libvirt.virDomain) -> Dict:
        """
        Get comprehensive VM information
        
        Args:
            domain: libvirt domain object
            
        Returns:
            Dictionary with VM details
        """
        try:
            state, reason = domain.state()
            info = domain.info()
            
            return {
                'name': domain.name(),
                'uuid': domain.UUIDString(),
                'state': state,
                'state_name': VMState.STATE_NAMES.get(state, "Unknown"),
                'is_active': domain.isActive() == 1,
                'is_persistent': domain.isPersistent() == 1,
                'max_memory': info[1],  # KB
                'memory': info[2],  # KB
                'vcpus': info[3],
                'cpu_time': info[4],  # nanoseconds
                'autostart': domain.autostart() == 1
            }
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get VM info: {e}")
            return {}
    
    def start_vm(self, domain: libvirt.virDomain) -> bool:
        """
        Start a VM
        
        Args:
            domain: libvirt domain object
            
        Returns:
            bool: Success status
        """
        try:
            if domain.isActive():
                logger.warning(f"VM '{domain.name()}' is already running")
                return True
            
            domain.create()
            logger.info(f"VM '{domain.name()}' started successfully")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to start VM '{domain.name()}': {e}")
            return False
    
    def start_vm_with_viewer(
        self,
        domain: libvirt.virDomain,
        fullscreen: bool = False
    ) -> bool:
        """
        Start VM and automatically launch viewer
        
        Args:
            domain: libvirt domain object
            fullscreen: Launch viewer in fullscreen
        
        Returns:
            bool: Success status
        """
        try:
            vm_name = domain.name()

            if not domain.isActive():
                logger.info(f"Starting VM '{vm_name}'...")
                domain.create()
                time.sleep(2)

            success = self.viewer_manager.launch_viewer(
                vm_name,
                domain,
                wait_for_vm=True,
                fullscreen=fullscreen
            )

            if success:
                logger.info(f"VM '{vm_name}' started with viewer")
                return True
            else:
                logger.warning("VM started but viewer launch failed")
                return True

        except libvirt.libvirtError as e:
            logger.error(f"Failed to start VM: {e}")
            return False

    def stop_vm(self, domain: libvirt.virDomain, force: bool = False) -> bool:
        """
        Stop a VM
        
        Args:
            domain: libvirt domain object
            force: Force stop (destroy) instead of graceful shutdown
            
        Returns:
            bool: Success status
        """
        try:
            if not domain.isActive():
                logger.warning(f"VM '{domain.name()}' is not running")
                return True
            
            # Check if VM has GPU passthrough enabled
            has_gpu_passthrough = self._check_gpu_passthrough(domain)
            
            if force:
                domain.destroy()
                logger.info(f"VM '{domain.name()}' force stopped")
            else:
                domain.shutdown()
                logger.info(f"VM '{domain.name()}' shutdown initiated")
            
            # If GPU passthrough is enabled, unbind GPU from VFIO after VM stops
            if has_gpu_passthrough:
                logger.info(f"VM '{domain.name()}' has GPU passthrough, will restore GPU to host")
                self._restore_gpu_to_host_after_stop(domain)
            
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to stop VM '{domain.name()}': {e}")
            return False
    
    def _check_gpu_passthrough(self, domain: libvirt.virDomain) -> bool:
        """
        Check if VM has GPU passthrough enabled by examining XML
        
        Args:
            domain: libvirt domain object
            
        Returns:
            bool: True if GPU passthrough is configured
        """
        try:
            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)
            devices = root.find('devices')
            
            if devices is not None:
                # Look for PCI hostdev devices (GPU passthrough)
                for hostdev in devices.findall('hostdev'):
                    if hostdev.get('type') == 'pci':
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to check GPU passthrough: {e}")
            return False
    
    def _restore_gpu_to_host_after_stop(self, domain: libvirt.virDomain):
        """
        Wait for VM to stop, then restore GPU to host
        
        Args:
            domain: libvirt domain object
        """
        import threading
        
        def wait_and_restore():
            vm_name = domain.name()
            logger.info(f"Waiting for VM '{vm_name}' to stop...")
            
            # Wait for VM to fully stop (max 30 seconds)
            for _ in range(30):
                try:
                    if not domain.isActive():
                        logger.info(f"VM '{vm_name}' stopped, restoring GPU to host...")
                        
                        # Import here to avoid circular dependency
                        from backend.gpu_detector import GPUDetector
                        from backend.vfio_manager import VFIOManager
                        
                        detector = GPUDetector()
                        passthrough_gpus = detector.get_passthrough_gpus()
                        
                        if passthrough_gpus:
                            gpu = passthrough_gpus[0]  # Assume first GPU
                            vfio_manager = VFIOManager()
                            
                            # Only unbind from VFIO, don't modify XML (already stopped)
                            logger.info(f"Restoring {gpu.full_name} to host driver...")
                            if vfio_manager.unbind_gpu_from_vfio(gpu):
                                logger.info("GPU successfully restored to host")
                            else:
                                logger.warning("Failed to restore GPU to host")
                        
                        return
                except Exception as e:
                    logger.debug(f"Waiting for VM stop: {e}")
                
                time.sleep(1)
            
            logger.warning(f"Timeout waiting for VM '{vm_name}' to stop")
        
        # Run in background thread to not block UI
        thread = threading.Thread(target=wait_and_restore, daemon=True)
        thread.start()

    def stop_vm_and_close_viewer(self, domain: libvirt.virDomain, force: bool = False) -> bool:
        """
        Stop VM and close viewer
        
        Args:
            domain: libvirt domain object
            force: Force stop (destroy)
        
        Returns:
            bool: Success status
        """
        vm_name = domain.name()

        success = self.stop_vm(domain, force)

        self.viewer_manager.close_viewer(vm_name)

        return success
    
    def reboot_vm(self, domain: libvirt.virDomain) -> bool:
        """
        Reboot a VM
        
        Args:
            domain: libvirt domain object
            
        Returns:
            bool: Success status
        """
        try:
            domain.reboot()
            logger.info(f"VM '{domain.name()}' reboot initiated")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to reboot VM: {e}")
            return False
    
    def pause_vm(self, domain: libvirt.virDomain) -> bool:
        """Pause a running VM"""
        try:
            if not domain.isActive():
                logger.warning(f"VM '{domain.name()}' is not running")
                return False
            
            domain.suspend()
            logger.info(f"VM '{domain.name()}' paused")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to pause VM: {e}")
            return False
    
    def resume_vm(self, domain: libvirt.virDomain) -> bool:
        """Resume a paused VM"""
        try:
            domain.resume()
            logger.info(f"VM '{domain.name()}' resumed")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to resume VM: {e}")
            return False
    
    def set_autostart(self, domain: libvirt.virDomain, enable: bool) -> bool:
        """
        Set VM autostart on host boot
        
        Args:
            domain: libvirt domain object
            enable: Enable or disable autostart
            
        Returns:
            bool: Success status
        """
        try:
            domain.setAutostart(1 if enable else 0)
            status = "enabled" if enable else "disabled"
            logger.info(f"Autostart {status} for VM '{domain.name()}'")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to set autostart: {e}")
            return False
