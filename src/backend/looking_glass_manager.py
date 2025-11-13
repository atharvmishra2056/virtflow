"""
Looking Glass Manager - Setup and manage Looking Glass for GPU passthrough viewing
"""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from utils.logger import logger


class LookingGlassManager:
    """Manages Looking Glass configuration for VMs"""
    
    def __init__(self):
        self.looking_glass_installed = self._check_looking_glass()
    
    def _check_looking_glass(self) -> bool:
        """Check if Looking Glass client is installed"""
        result = subprocess.run(['which', 'looking-glass-client'], capture_output=True)
        return result.returncode == 0
    
    def setup_vm_for_looking_glass(self, domain, ram_size_mb: int = 128) -> bool:
        """
        Configure VM for Looking Glass
        
        Args:
            domain: libvirt domain object
            ram_size_mb: Shared memory size in MB (32/64/128 depending on resolution)
        
        Returns:
            bool: Success status
        """
        try:
            vm_name = domain.name()
            logger.info(f"Configuring Looking Glass for '{vm_name}'...")
            
            # Stop VM if running
            if domain.isActive():
                logger.info("Stopping VM to apply Looking Glass configuration...")
                domain.destroy()
                import time
                time.sleep(2)
            
            # Parse VM XML
            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)
            devices = root.find('devices')
            
            if devices is None:
                logger.error("No devices section in VM XML")
                return False
            
            # Remove existing IVSHMEM devices
            for shmem in list(devices.findall('shmem')):
                logger.info("Removing existing IVSHMEM device")
                devices.remove(shmem)
            
            # Add IVSHMEM device for Looking Glass
            logger.info(f"Adding IVSHMEM device ({ram_size_mb}MB)")
            shmem = ET.SubElement(devices, 'shmem')
            shmem.set('name', 'looking-glass')
            
            model = ET.SubElement(shmem, 'model')
            model.set('type', 'ivshmem-plain')
            
            size = ET.SubElement(shmem, 'size')
            size.set('unit', 'M')
            size.text = str(ram_size_mb)
            
            # Ensure QXL video device exists - Looking Glass host needs it to capture!
            # Remove all existing video devices first
            for video in list(devices.findall('video')):
                logger.info(f"Removing existing video device")
                devices.remove(video)
            
            # Add QXL as the only video device
            logger.info("Adding QXL video device for Looking Glass capture")
            video = ET.SubElement(devices, 'video')
            model = ET.SubElement(video, 'model')
            model.set('type', 'qxl')
            model.set('ram', '65536')
            model.set('vram', '65536')
            model.set('vgamem', '16384')
            model.set('heads', '1')
            model.set('primary', 'yes')
            
            # Keep SPICE for input only (keyboard/mouse)
            has_spice = any(g.get('type') == 'spice' for g in devices.findall('graphics'))
            if not has_spice:
                logger.info("Adding SPICE for input devices")
                graphics = ET.SubElement(devices, 'graphics')
                graphics.set('type', 'spice')
                graphics.set('autoport', 'yes')
                graphics.set('listen', '127.0.0.1')
                listen = ET.SubElement(graphics, 'listen')
                listen.set('type', 'address')
                listen.set('address', '127.0.0.1')
            
            # Write back XML
            new_xml = ET.tostring(root, encoding='unicode')
            
            # Get connection from domain
            conn = domain.connect()
            conn.defineXML(new_xml)
            
            logger.info(f"Looking Glass configuration applied to '{vm_name}'")
            logger.info("Next steps:")
            logger.info("1. Start the VM")
            logger.info("2. Install Looking Glass host application in Windows")
            logger.info("3. Launch Looking Glass client on host")
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to configure Looking Glass: {e}")
            return False
    
    def create_shmem_file(self, ram_size_mb: int = 128) -> bool:
        """
        Create shared memory file for Looking Glass
        
        Args:
            ram_size_mb: Size in MB
        
        Returns:
            bool: Success status
        """
        try:
            shmem_path = Path("/dev/shm/looking-glass")
            
            logger.info(f"Creating shared memory file: {shmem_path}")
            
            # Remove if exists
            if shmem_path.exists():
                logger.info("Removing existing shared memory file")
                subprocess.run(['sudo', 'rm', '-f', str(shmem_path)], check=True)
            
            # Create file using dd (more reliable than touch + truncate)
            logger.info(f"Creating {ram_size_mb}MB shared memory file")
            subprocess.run([
                'sudo', 'dd',
                'if=/dev/zero',
                f'of={shmem_path}',
                'bs=1M',
                f'count={ram_size_mb}'
            ], check=True, capture_output=True)
            
            # Set permissions (allow qemu user)
            logger.info("Setting ownership and permissions")
            subprocess.run([
                'sudo', 'chown', 'libvirt-qemu:kvm', str(shmem_path)
            ], check=True)
            
            subprocess.run([
                'sudo', 'chmod', '660', str(shmem_path)
            ], check=True)
            
            logger.info("Shared memory file created successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.cmd}")
            logger.error(f"Return code: {e.returncode}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.exception(f"Failed to create shared memory file: {e}")
            return False
    
    def install_looking_glass_client(self) -> tuple[bool, str]:
        """
        Install Looking Glass client on host
        
        Returns:
            tuple[bool, str]: (Success status, message)
        """
        try:
            logger.info("Installing Looking Glass client...")
            
            # Check if already installed
            if self.looking_glass_installed:
                logger.info("Looking Glass client already installed")
                return True, "Already installed"
            
            # Try to install from package manager first
            result = subprocess.run([
                'sudo', 'apt', 'install', '-y', 'looking-glass-client'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Looking Glass client installed from apt")
                self.looking_glass_installed = True
                return True, "Installed from apt repository"
            
            # Not in apt, need to build from source
            logger.info("Looking Glass not in apt, building from source...")
            
            # Run installation script
            import os
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'install_looking_glass.sh'
            )
            
            if not os.path.exists(script_path):
                return False, "Installation script not found"
            
            logger.info(f"Running installation script: {script_path}")
            
            # Run script in terminal so user can see progress
            result = subprocess.run([
                'x-terminal-emulator', '-e',
                f'bash -c "{script_path}; echo; echo Press Enter to close...; read"'
            ])
            
            # Check if installed now
            self.looking_glass_installed = self._check_looking_glass()
            
            if self.looking_glass_installed:
                return True, "Built and installed from source"
            else:
                return False, "Installation script completed but client not found"
                
        except Exception as e:
            logger.exception(f"Failed to install Looking Glass: {e}")
            return False, str(e)
    
    def get_windows_host_download_url(self) -> str:
        """Get download URL for Looking Glass Windows host application"""
        return "https://looking-glass.io/artifact/stable/host"
    
    def launch_looking_glass_client(self, vm_name: str = None) -> subprocess.Popen:
        """
        Launch Looking Glass client
        
        Args:
            vm_name: Optional VM name for window title
        
        Returns:
            subprocess.Popen: Client process
        """
        try:
            cmd = ['looking-glass-client']
            
            if vm_name:
                cmd.extend(['-f', '/dev/shm/looking-glass'])
            
            logger.info(f"Launching Looking Glass client: {' '.join(cmd)}")
            process = subprocess.Popen(cmd)
            
            return process
            
        except Exception as e:
            logger.exception(f"Failed to launch Looking Glass client: {e}")
            return None
