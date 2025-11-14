"""
VM Viewer Manager - Handles external SPICE/VNC viewer integration
Automatically launches virt-viewer when VM starts
"""

import subprocess
import time
import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from pathlib import Path

import libvirt

from utils.logger import logger


class VMViewerManager:
    """Manages VM display viewer (virt-viewer/remote-viewer)"""
    
    def __init__(self):
        self.viewer_processes = {}  # vm_name -> subprocess.Popen
        self.lg_window = None
        self._check_viewer_available()
    
    def _check_viewer_available(self) -> bool:
        """Check if virt-viewer or remote-viewer is available"""
        import shutil
        
        self.viewer_binary = None
        
        # Try virt-viewer first (preferred)
        if shutil.which('virt-viewer'):
            self.viewer_binary = 'virt-viewer'
            logger.info("Found virt-viewer")
            return True
        
        # Fallback to remote-viewer
        if shutil.which('remote-viewer'):
            self.viewer_binary = 'remote-viewer'
            logger.info("Found remote-viewer")
            return True
        
        logger.warning("No SPICE/VNC viewer found (virt-viewer or remote-viewer)")
        return False
    
    def get_vm_display_info(self, domain: libvirt.virDomain) -> Optional[Tuple[str, str, int]]:
        """
        Get VM display connection info
        
        Args:
            domain: libvirt domain object
            
        Returns:
            Tuple of (protocol, host, port) or None
        """
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            # Find graphics element
            graphics = root.find('.//devices/graphics')
            
            if graphics is not None:
                protocol = graphics.get('type')  # 'spice' or 'vnc'
                host = graphics.get('listen', '127.0.0.1')
                port = graphics.get('port', 'auto')
                
                # Handle autoport
                if port == 'auto' or port == '-1':
                    # Get actual port from QEMU monitor
                    port = self._get_actual_port(domain, protocol)
                
                logger.info(f"VM display: {protocol}://{host}:{port}")
                return (protocol, host, int(port) if port else 0)
            
        except Exception as e:
            logger.error(f"Failed to get display info: {e}")
        
        return None
    
    def _get_actual_port(self, domain: libvirt.virDomain, protocol: str) -> Optional[int]:
        """Get actual SPICE/VNC port assigned by libvirt"""
        try:
            # Use virsh domdisplay to get connection URI
            result = subprocess.run(
                ['virsh', 'domdisplay', domain.name()],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                uri = result.stdout.strip()
                # Parse URI: spice://127.0.0.1:5900 or vnc://127.0.0.1:5901
                if '://' in uri and ':' in uri:
                    port_str = uri.split(':')[-1]
                    return int(port_str)
        except Exception as e:
            logger.debug(f"Failed to get actual port: {e}")
        
        return None
    
    def _check_looking_glass_configured(self, domain: libvirt.virDomain) -> bool:
        """Check if VM has Looking Glass IVSHMEM device configured"""
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            # Check for IVSHMEM device named 'looking-glass'
            for shmem in root.findall('.//devices/shmem'):
                if shmem.get('name') == 'looking-glass':
                    logger.info(f"VM has Looking Glass configured")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to check Looking Glass config: {e}")
            return False
    
    def launch_viewer(
        self,
        vm_name: str,
        domain: libvirt.virDomain,
        wait_for_vm: bool = True,
        fullscreen: bool = False
    ) -> bool:
        """
        Launch external SPICE/VNC viewer or Looking Glass for VM
        
        Args:
            vm_name: VM name
            domain: libvirt domain object
            wait_for_vm: Wait for VM to start before launching viewer
            fullscreen: Launch viewer in fullscreen mode
            
        Returns:
            bool: Success status
        """
        # Check if VM has Looking Glass configured
        if self._check_looking_glass_configured(domain):
            logger.info(f"VM has Looking Glass, launching Looking Glass client...")
            return self._launch_looking_glass(vm_name, domain)
        
        if not self.viewer_binary:
            logger.error("No viewer binary available")
            return False
        
        # Check if viewer already running for this VM
        if vm_name in self.viewer_processes:
            proc = self.viewer_processes[vm_name]
            if proc.poll() is None:  # Still running
                logger.info(f"Viewer already running for '{vm_name}'")
                return True
        
        logger.info(f"Launching viewer for VM '{vm_name}'...")
        
        try:
            # Build viewer command
            cmd = [
                self.viewer_binary,
                '--connect', 'qemu:///system',
                '--wait' if wait_for_vm else '--reconnect',
                vm_name
            ]
            
            if fullscreen:
                cmd.append('--full-screen')
            
            # Launch viewer as separate process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            
            self.viewer_processes[vm_name] = process
            logger.info(f"Viewer launched for '{vm_name}' (PID: {process.pid})")
            return True
            
        except FileNotFoundError:
            logger.error(f"Viewer binary not found: {self.viewer_binary}")
            return False
        except Exception as e:
            logger.error(f"Failed to launch viewer: {e}")
            return False
    
    def close_viewer(self, vm_name: str) -> bool:
        """
        Close viewer for a VM
        
        Args:
            vm_name: VM name
            
        Returns:
            bool: Success status
        """
        if vm_name not in self.viewer_processes:
            return True
        
        process = self.viewer_processes[vm_name]
        
        try:
            if process.poll() is None:  # Still running
                logger.info(f"Closing viewer for '{vm_name}'...")
                process.terminate()
                
                # Wait for graceful termination
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    process.kill()
                    process.wait()
            
            del self.viewer_processes[vm_name]
            logger.info(f"Viewer closed for '{vm_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close viewer: {e}")
            return False
    
    def is_viewer_running(self, vm_name: str) -> bool:
        """Check if viewer is running for a VM"""
        if vm_name not in self.viewer_processes:
            return False
        
        process = self.viewer_processes[vm_name]
        return process.poll() is None
    
    def launch_looking_glass_windowed(self, vm_name: str, vm_host: str = "localhost", vm_port: int = 5900) -> bool:
        """Launch Looking Glass with proper window decorations"""
        try:
            from ui.looking_glass_window_v2 import LookingGlassWindowV2
            
            self.lg_window = LookingGlassWindowV2(vm_name, vm_host, vm_port)
            self.lg_window.window_closed.connect(lambda: self._on_lg_window_closed(vm_name))
            self.lg_window.show()
            return True
        except Exception as e:
            logger.exception(f"Failed to launch Looking Glass: {e}")
            return False
    
    def _on_lg_window_closed(self, vm_name: str):
        """Handle Looking Glass window closure"""
        logger.info(f"Looking Glass window closed for {vm_name}")
        if hasattr(self, 'lg_window'):
            self.lg_window = None
    
    def _launch_looking_glass(self, vm_name: str, domain: libvirt.virDomain) -> bool:
        """
        Launch Looking Glass client for VM
        
        Args:
            vm_name: VM name
            domain: libvirt domain object
            
        Returns:
            bool: Success status
        """
        try:
            # Check if Looking Glass client is installed
            import shutil
            if not shutil.which('looking-glass-client'):
                logger.error("Looking Glass client not installed")
                logger.info("Install with: Click 'Install Looking Glass' button")
                return False
            
            # Check if viewer already running
            if vm_name in self.viewer_processes:
                proc = self.viewer_processes[vm_name]
                if proc.poll() is None:
                    logger.info(f"Looking Glass already running for '{vm_name}'")
                    return True
            
            logger.info("Launching Looking Glass client...")
            
            # Get SPICE connection info for keyboard/mouse
            spice_result = subprocess.run(
                ['virsh', 'domdisplay', vm_name],
                capture_output=True,
                text=True
            )
            
            spice_uri = spice_result.stdout.strip()
            logger.info(f"SPICE URI: {spice_uri}")
            
            # Extract host and port from spice://127.0.0.1:5900
            spice_args = []
            if spice_uri.startswith('spice://'):
                spice_host_port = spice_uri.replace('spice://', '')
                if ':' in spice_host_port:
                    host, port = spice_host_port.split(':')
                    spice_args = ['spice:host=' + host, 'spice:port=' + port]
                    logger.info(f"Using SPICE: host={host}, port={port}")
            
            # Build Looking Glass command with config file
            import os
            config_file = os.path.join(os.path.dirname(__file__), 'looking_glass.conf')
            
            lg_args = [
                'looking-glass-client',
                '-f', '/dev/shm/looking-glass',
                '-p', '0',  # Manual capture with ScrollLock
                '-C', config_file  # Use config file for window settings
            ]
            
            # Add SPICE connection if available
            if spice_args:
                lg_args.extend(spice_args)
            
            logger.info(f"Launching: {' '.join(lg_args)}")
            logger.info(f"Using config file: {config_file}")
            
            # Set up environment for window decorations on Wayland
            env = os.environ.copy()
            # Force GTK to use client-side decorations
            env['GTK_CSD'] = '1'
            # Try to use Xwayland for better window management
            env['GDK_BACKEND'] = 'x11'
            # Force GNOME window decorations
            env['XDG_CURRENT_DESKTOP'] = 'GNOME'
            # Enable libdecor if available
            env['LIBDECOR_PLUGIN_DIR'] = '/usr/lib/x86_64-linux-gnu/libdecor-0'
            # Disable fullscreen on startup
            env['WAYLAND_DISPLAY'] = os.environ.get('WAYLAND_DISPLAY', 'wayland-0')
            
            # Launch Looking Glass
            process = subprocess.Popen(
                lg_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env=env
            )
            
            self.viewer_processes[vm_name] = process
            logger.info(f"Looking Glass launched successfully for '{vm_name}' (PID: {process.pid})")
            
            # Try to apply window decorations using wmctrl
            import time
            import shutil
            time.sleep(1.5)  # Give window time to appear
            
            if shutil.which('wmctrl'):
                try:
                    # List all windows and find the Looking Glass one
                    result = subprocess.run(
                        ['wmctrl', '-l'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    
                    # Find window with "looking-glass" in the name
                    for line in result.stdout.split('\n'):
                        if 'looking-glass' in line.lower():
                            # Extract window ID (first field)
                            window_id = line.split()[0]
                            logger.info(f"Found Looking Glass window: {window_id}")
                            
                            # Try to unmaximize and resize
                            subprocess.run(
                                ['wmctrl', '-i', '-r', window_id, '-b', 'remove,maximized_vert,maximized_horz'],
                                capture_output=True,
                                timeout=2
                            )
                            # Resize window
                            subprocess.run(
                                ['wmctrl', '-i', '-r', window_id, '-e', '0,300,200,1024,768'],
                                capture_output=True,
                                timeout=2
                            )
                            logger.info(f"Applied window management to {window_id}")
                            break
                except Exception as e:
                    logger.debug(f"Could not apply wmctrl decorations: {e}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to launch Looking Glass: {e}")
            return False
    
    def close_all_viewers(self):
        """Close all running viewers"""
        vm_names = list(self.viewer_processes.keys())
        for vm_name in vm_names:
            self.close_viewer(vm_name)
