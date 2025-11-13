"""
Guest Driver Helper - Automates driver installation in Windows guests
Uses QEMU Guest Agent to communicate with guest OS and install drivers
"""

import json
import time
import subprocess
import requests
from typing import Optional, Dict, Tuple
from pathlib import Path

from backend.gpu_detector import GPU
from backend.libvirt_manager import LibvirtManager
from utils.logger import logger


class GuestDriverHelper:
    """Manages guest OS driver installation via QEMU Guest Agent"""
    
    NVIDIA_VENDOR_ID = "10de"
    AMD_VENDOR_ID = "1002"
    
    # Driver download URLs (latest stable versions)
    NVIDIA_DRIVER_BASE_URL = "https://us.download.nvidia.com/Windows/{version}/latest.exe"
    AMD_DRIVER_BASE_URL = "https://drivers.amd.com/drivers/installer/latest.exe"
    
    def __init__(self, manager: LibvirtManager):
        """
        Initialize guest driver helper
        
        Args:
            manager: LibvirtManager instance
        """
        self.manager = manager
    
    def check_guest_agent_ready(self, vm_name: str, timeout: int = 60) -> bool:
        """
        Check if QEMU Guest Agent is ready in the VM
        
        Args:
            vm_name: VM name
            timeout: Timeout in seconds
            
        Returns:
            bool: True if agent is ready
        """
        logger.info(f"Waiting for guest agent in '{vm_name}'...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ['virsh', 'qemu-agent-command', vm_name,
                     '{"execute":"guest-ping"}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    logger.info(f"Guest agent ready in '{vm_name}'")
                    return True
                    
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                logger.debug(f"Guest agent check failed: {e}")
            
            time.sleep(2)
        
        logger.warning(f"Guest agent not ready after {timeout}s")
        return False
    
    def get_guest_os_info(self, vm_name: str) -> Optional[Dict]:
        """
        Get guest OS information via guest agent
        
        Args:
            vm_name: VM name
            
        Returns:
            Dictionary with OS info or None
        """
        try:
            result = subprocess.run(
                ['virsh', 'qemu-agent-command', vm_name,
                 '{"execute":"guest-get-osinfo"}', '--pretty'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                os_info = data.get('return', {})
                logger.info(f"Guest OS: {os_info.get('name')} {os_info.get('version')}")
                return os_info
                
        except Exception as e:
            logger.error(f"Failed to get guest OS info: {e}")
        
        return None
    
    def execute_guest_command(
        self,
        vm_name: str,
        command: str,
        args: list,
        capture_output: bool = True,
        timeout: int = 300
    ) -> Tuple[bool, Optional[str]]:
        """
        Execute command in guest via guest agent
        
        Args:
            vm_name: VM name
            command: Command/executable path
            args: Command arguments
            capture_output: Capture command output
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (success, output)
        """
        try:
            # Build guest-exec command
            exec_cmd = {
                "execute": "guest-exec",
                "arguments": {
                    "path": command,
                    "arg": args,
                    "capture-output": capture_output
                }
            }
            
            # Execute command
            result = subprocess.run(
                ['virsh', 'qemu-agent-command', vm_name,
                 json.dumps(exec_cmd)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to execute guest command: {result.stderr}")
                return False, None
            
            # Parse PID
            exec_result = json.loads(result.stdout)
            pid = exec_result.get('return', {}).get('pid')
            
            if not pid:
                logger.error("No PID returned from guest-exec")
                return False, None
            
            logger.debug(f"Guest command started with PID {pid}")
            
            # Wait for command completion
            start_time = time.time()
            while time.time() - start_time < timeout:
                status_cmd = {
                    "execute": "guest-exec-status",
                    "arguments": {"pid": pid}
                }
                
                status_result = subprocess.run(
                    ['virsh', 'qemu-agent-command', vm_name,
                     json.dumps(status_cmd)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if status_result.returncode == 0:
                    status_data = json.loads(status_result.stdout)
                    status_info = status_data.get('return', {})
                    
                    if status_info.get('exited'):
                        exit_code = status_info.get('exitcode', -1)
                        
                        # Get output if captured
                        output = None
                        if capture_output and 'out-data' in status_info:
                            import base64
                            output = base64.b64decode(
                                status_info['out-data']
                            ).decode('utf-8', errors='ignore')
                        
                        success = exit_code == 0
                        logger.info(f"Guest command completed with exit code {exit_code}")
                        return success, output
                
                time.sleep(2)
            
            logger.warning(f"Guest command timed out after {timeout}s")
            return False, None
            
        except Exception as e:
            logger.error(f"Failed to execute guest command: {e}")
            return False, None
    
    def check_virtio_drivers_installed(self, vm_name: str) -> bool:
        """
        Check if VirtIO drivers are installed in Windows guest
        
        Args:
            vm_name: VM name
            
        Returns:
            bool: True if VirtIO drivers are installed
        """
        logger.info(f"Checking VirtIO drivers in '{vm_name}'...")
        
        # Check for Red Hat VirtIO SCSI controller
        success, output = self.execute_guest_command(
            vm_name,
            "powershell.exe",
            ["-Command", "Get-PnpDevice -FriendlyName '*VirtIO*' | Select-Object Status"]
        )
        
        if success and output and "OK" in output:
            logger.info("VirtIO drivers detected and working")
            return True
        
        logger.warning("VirtIO drivers not detected or not working")
        return False
    
    def detect_gpu_in_guest(self, vm_name: str, gpu_vendor_id: str) -> bool:
        """
        Check if GPU is detected in Windows guest
        
        Args:
            vm_name: VM name
            gpu_vendor_id: PCI vendor ID (10de for NVIDIA, 1002 for AMD)
            
        Returns:
            bool: True if GPU detected
        """
        logger.info(f"Checking for GPU in guest (vendor {gpu_vendor_id})...")
        
        # Use PowerShell to check PCI devices
        success, output = self.execute_guest_command(
            vm_name,
            "powershell.exe",
            ["-Command", 
             "Get-PnpDevice -Class Display | Select-Object FriendlyName,Status"]
        )
        
        if success and output:
            if gpu_vendor_id == self.NVIDIA_VENDOR_ID:
                if "NVIDIA" in output:
                    logger.info("NVIDIA GPU detected in guest")
                    return True
            elif gpu_vendor_id == self.AMD_VENDOR_ID:
                if "AMD" in output or "Radeon" in output:
                    logger.info("AMD GPU detected in guest")
                    return True
        
        logger.info("GPU not yet detected in guest")
        return False
    
    def get_gpu_driver_download_url(self, gpu: GPU) -> Optional[str]:
        """
        Get GPU driver download URL for given GPU
        
        Args:
            gpu: GPU object
            
        Returns:
            Download URL or None
        """
        vendor_id = gpu.pci_device.vendor_id
        
        if vendor_id == self.NVIDIA_VENDOR_ID:
            # NVIDIA driver URL (Game Ready Driver)
            # Note: In production, you'd query NVIDIA API for latest version
            return "https://us.download.nvidia.com/Windows/565.90/565.90-desktop-win10-win11-64bit-international-dch-whql.exe"
        
        elif vendor_id == self.AMD_VENDOR_ID:
            # AMD Adrenalin driver URL
            return "https://drivers.amd.com/drivers/installer/23.40/whql/amd-software-adrenalin-edition-23.40.03.01-win10-win11-dec5-rdna.exe"
        
        return None
    
    def download_gpu_driver(self, gpu: GPU, dest_path: str) -> bool:
        """
        Download GPU driver to host
        
        Args:
            gpu: GPU object
            dest_path: Destination path on host
            
        Returns:
            bool: Success status
        """
        url = self.get_gpu_driver_download_url(gpu)
        
        if not url:
            logger.error(f"No driver URL available for {gpu.vendor}")
            return False
        
        logger.info(f"Downloading {gpu.vendor} driver from {url}...")
        
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"Download progress: {progress:.1f}%")
            
            logger.info(f"Driver downloaded to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download driver: {e}")
            return False
    
    def copy_file_to_guest(
        self,
        vm_name: str,
        host_path: str,
        guest_path: str
    ) -> bool:
        """
        Copy file from host to guest via guest agent
        
        Args:
            vm_name: VM name
            host_path: Path on host
            guest_path: Path in guest
            
        Returns:
            bool: Success status
        """
        logger.info(f"Copying {host_path} to guest:{guest_path}")
        
        try:
            # Read file content and encode to base64
            with open(host_path, 'rb') as f:
                content = f.read()
            
            import base64
            content_b64 = base64.b64encode(content).decode('ascii')
            
            # Write file to guest
            write_cmd = {
                "execute": "guest-file-write",
                "arguments": {
                    "path": guest_path,
                    "content": content_b64,
                    "base64": True
                }
            }
            
            # Note: guest-file-write might not be available in all guest agents
            # Alternative: Use PowerShell to download from a temp web server
            # For simplicity, we'll use a shared folder approach in production
            
            logger.warning("File copy via guest agent requires additional setup")
            logger.info("Alternative: Use shared folder or SMB mount")
            return False
            
        except Exception as e:
            logger.error(f"Failed to copy file to guest: {e}")
            return False
    
    def install_gpu_driver_in_guest(
        self,
        vm_name: str,
        gpu: GPU,
        driver_path_in_guest: str
    ) -> bool:
        """
        Install GPU driver in Windows guest (silent installation)
        
        Args:
            vm_name: VM name
            gpu: GPU object
            driver_path_in_guest: Path to driver installer in guest
            
        Returns:
            bool: Success status
        """
        vendor_id = gpu.pci_device.vendor_id
        
        if vendor_id == self.NVIDIA_VENDOR_ID:
            logger.info("Installing NVIDIA driver (silent mode)...")
            
            # NVIDIA silent install command
            # Extract driver first, then run setup.exe
            success, output = self.execute_guest_command(
                vm_name,
                driver_path_in_guest,
                ["-s", "-noreboot", "-noeula"],
                capture_output=True,
                timeout=600  # 10 minutes
            )
            
            if success:
                logger.info("NVIDIA driver installed successfully")
                return True
            else:
                logger.error(f"NVIDIA driver installation failed: {output}")
                return False
        
        elif vendor_id == self.AMD_VENDOR_ID:
            logger.info("Installing AMD driver (silent mode)...")
            
            # AMD silent install command
            success, output = self.execute_guest_command(
                vm_name,
                driver_path_in_guest,
                ["-install", "-log", "C:\\amd_install.log"],
                capture_output=True,
                timeout=600
            )
            
            if success:
                logger.info("AMD driver installed successfully")
                return True
            else:
                logger.error(f"AMD driver installation failed: {output}")
                return False
        
        logger.error(f"Unsupported GPU vendor: {vendor_id}")
        return False
    
    def request_guest_reboot(self, vm_name: str) -> bool:
        """
        Request guest to reboot via guest agent
        
        Args:
            vm_name: VM name
            
        Returns:
            bool: Success status
        """
        logger.info(f"Requesting reboot of '{vm_name}'...")
        
        try:
            result = subprocess.run(
                ['virsh', 'reboot', vm_name, '--mode', 'agent'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Guest '{vm_name}' reboot initiated")
                return True
            else:
                logger.error(f"Failed to reboot guest: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to request guest reboot: {e}")
            return False
