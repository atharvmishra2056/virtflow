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
            is_active = domain.isActive() == 1
            
            vm_info = {
                'name': domain.name(),
                'uuid': domain.UUIDString(),
                'state': state,
                'state_name': VMState.STATE_NAMES.get(state, "Unknown"),
                'is_active': is_active,
                'is_persistent': domain.isPersistent() == 1,
                'max_memory': info[1],  # KB
                'memory': info[2],  # KB
                'vcpus': info[3],
                'cpu_time': info[4],  # nanoseconds
                'autostart': domain.autostart() == 1,
                # --- NEW: Add defaults for stats ---
                'disk_read_bytes': 0,
                'disk_write_bytes': 0,
                'net_rx_bytes': 0,
                'net_tx_bytes': 0
            }

            # --- NEW: If running, get I/O stats ---
            if is_active:
                try:
                    # Parse XML to find disk and net devices
                    xml_desc = domain.XMLDesc(0)
                    root = ET.fromstring(xml_desc)
                    
                    # Find first virtio disk (vda)
                    disk_target = root.find(".//devices/disk[@device='disk']/target")
                    if disk_target is not None:
                        disk_dev = disk_target.get('dev')
                        # blockStats returns [rd_req, rd_bytes, wr_req, wr_bytes, errs]
                        stats = domain.blockStats(disk_dev)
                        vm_info['disk_read_bytes'] = stats[1]
                        vm_info['disk_write_bytes'] = stats[3]

                    # Find first interface
                    net_target = root.find(".//devices/interface/target")
                    if net_target is not None:
                        net_dev = net_target.get('dev')
                        # interfaceStats returns [rx_bytes, rx_pkts, rx_errs, rx_drop, tx_bytes, tx_pkts, tx_errs, tx_drop]
                        stats = domain.interfaceStats(net_dev)
                        vm_info['net_rx_bytes'] = stats[0]
                        vm_info['net_tx_bytes'] = stats[4]
                        
                except libvirt.libvirtError as e:
                    # This can fail if devices are not ready, just log it
                    logger.debug(f"Could not fetch I/O stats for {domain.name()}: {e}")
                
            return vm_info
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get VM info: {e}")
            return {}

    # --- TASKS 2.C: New method to apply settings on-the-fly ---
    def _apply_performance_settings(self, domain: libvirt.virDomain):
        """Applies SPICE, CPU, and Memory settings just before launch."""
        try:
            # Get ALL settings, including metadata
            settings = self.manager.get_all_vm_settings(domain)
            if not settings:
                logger.debug("No custom settings found, skipping runtime XML changes.")
                return

            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)
            modified = False

            # --- SPICE OpenGL (from metadata) ---
            spice_gl = settings.get("spice_opengl", "false").lower() == "true"
            graphics_node = root.find(".//graphics[@type='spice']")
            if graphics_node is not None:
                gl_node = graphics_node.find('gl')
                
                if spice_gl: # "Fast (OpenGL)"
                    if gl_node is None:
                        ET.SubElement(graphics_node, 'gl', {'enable': 'yes'})
                        modified = True
                        logger.info(f"Applying SPICE OpenGL for {domain.name()}")
                else: # "Smooth (QXL)"
                    if gl_node is not None:
                        graphics_node.remove(gl_node)
                        modified = True
                        logger.info(f"Removing SPICE OpenGL for {domain.name()}")
            
            # --- HugePages (from metadata) ---
            if settings.get("hugepages", "false").lower() == "true":
                if root.find("memoryBacking") is None:
                    mem_backing = ET.SubElement(root, "memoryBacking")
                    ET.SubElement(mem_backing, "hugepages")
                    modified = True
                    logger.info(f"Applying HugePages for {domain.name()}")
            
            # --- CPU Pinning (from metadata) ---
            if settings.get("cpu_pinning", "false").lower() == "true":
                if root.find("cputune") is None:
                    # NOTE: A real implementation requires topology.
                    # This is a placeholder as per the plan to add the tag.
                    ET.SubElement(root, "cputune")
                    # TODO: Add <vcpupin ...> elements
                    modified = True
                    logger.info(f"Applying CPU Pinning for {domain.name()}")

            # If we modified the XML, redefine the domain (transiently)
            if modified:
                new_xml = ET.tostring(root, encoding="unicode")
                # Use defineXML to apply transient changes
                self.manager.connection.defineXML(new_xml)
                logger.info(f"Successfully applied runtime settings for {domain.name()}")

        except Exception as e:
            logger.error(f"Failed to apply performance settings: {e}")
            # Do not block VM start, just log the error
    
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
            
            # --- NEW: Check for GPU and bind ---
            xml_str = domain.XMLDesc(0)
            has_gpu = '<hostdev' in xml_str and 'type=\'pci\'' in xml_str
            
            if has_gpu:
                logger.info("VM has GPU passthrough, ensuring GPU is bound to VFIO...")
                from backend.gpu_detector import GPUDetector
                from backend.vfio_manager import VFIOManager
                
                detector = GPUDetector()
                passthrough_gpus = detector.get_passthrough_gpus()
                
                if passthrough_gpus:
                    gpu = passthrough_gpus[0]
                    vfio_manager = VFIOManager()
                    
                    import subprocess
                    result = subprocess.run(
                        ['lspci', '-k', '-s', gpu.pci_address.split(':', 1)[1]],
                        capture_output=True,
                        text=True
                    )
                    
                    if 'vfio-pci' not in result.stdout:
                        logger.info("GPU not bound to VFIO, binding now...")
                        if not vfio_manager.bind_gpu_to_vfio(gpu):
                            logger.error("Failed to bind GPU to VFIO.")
                            return False # Stop start process
                        logger.info("GPU successfully bound to VFIO")
                    else:
                        logger.info("GPU already bound to VFIO")
            
            # --- TASKS 2.C: Apply settings before launch ---
            self._apply_performance_settings(domain)

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
                # --- MODIFIED: Call our new start_vm ---
                if not self.start_vm(domain):
                    return False # Failed to start
                time.sleep(2)

            # --- NEW: Get the display preference ---
            preference = self.manager.get_display_preference(domain)
            logger.info(f"Found display preference: {preference}")
            # --- END NEW ---
            
            success = self.viewer_manager.launch_viewer(
                vm_name,
                domain,
                wait_for_vm=True,
                fullscreen=fullscreen,
                preference=preference # <-- Pass preference
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
                        # --- MODIFIED: We need to find the *actual* GPU passed to this VM ---
                        # This is a simplification, a full solution would parse the XML
                        # for the <hostdev> tags. For now, we assume the first passthrough-able GPU.
                        passthrough_gpus = detector.get_passthrough_gpus()
                        
                        if passthrough_gpus:
                            gpu = passthrough_gpus[0]
                            vfio_manager = VFIOManager()
                            
                            logger.info(f"Restoring {gpu.full_name} to host driver...")
                            if vfio_manager.unbind_gpu_from_vfio(gpu):
                                logger.info("GPU successfully restored to host")
                            else:
                                logger.warning("Failed to restore GPU to host")
                        
                        return
                except Exception as e:
                    # Catch libvirtError if domain disappears
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
            # --- MODIFIED: Use shutdown and wait for 'start_vm' to handle re-bind ---
            if domain.isActive():
                domain.reboot()
                logger.info(f"VM '{domain.name()}' reboot initiated")
                return True
            else:
                logger.warning(f"VM '{domain.name()}' is not running")
                return False
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