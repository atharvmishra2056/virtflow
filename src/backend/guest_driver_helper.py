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
    
    def _run_qemu_agent_command(self, vm_name: str, command: dict, timeout: int = 10) -> Tuple[bool, dict]:
        """Helper to run a QEMU Guest Agent command via virsh"""
        try:
            cmd_json = json.dumps(command)
            result = subprocess.run(
                ['virsh', 'qemu-agent-command', vm_name, cmd_json],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                logger.warning(f"qemu-agent-command failed for {vm_name}: {result.stderr}")
                return False, {"error": result.stderr.strip()}
            
            response = json.loads(result.stdout)
            return True, response
            
        except Exception as e:
            logger.error(f"Exception in qemu-agent-command: {e}")
            return False, {"error": str(e)}

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
                # Use guest-ping for a lightweight check
                success, response = self._run_qemu_agent_command(vm_name, {"execute": "guest-ping"})
                
                if success and "return" in response:
                    logger.info(f"Guest agent ready in '{vm_name}'")
                    return True
                    
            except Exception as e:
                logger.debug(f"Guest agent check failed: {e}")
            
            time.sleep(2)
        
        logger.warning(f"Guest agent not ready after {timeout}s")
        return False
    
    # --- TASK 1.4: New Method ---
    def install_virtio_drivers(self, vm_name: str) -> Tuple[bool, str]:
        """
        Attempts to find the virtio-win.iso and run the installer.
        """
        if not self.check_guest_agent_ready(vm_name):
            return False, "QEMU Guest Agent is not running. Please start the VM and ensure the agent is installed and running."
            
        # 1. Find the VirtIO CD-ROM drive letter
        logger.info(f"Searching for VirtIO ISO in '{vm_name}'...")
        success, response = self._run_qemu_agent_command(vm_name, {"execute": "guest-get-fsinfo"})
        
        if not success or "return" not in response:
            return False, f"Failed to query guest filesystems: {response.get('error')}"
        
        drive_letter = None
        for drive in response.get("return", []):
            if drive.get("type") == "cdrom" and "VIRTIO" in drive.get("fs-label", "").upper():
                drive_letter = drive.get("mountpoint")
                break
        
        if not drive_letter:
            return False, "Could not find an attached CD-ROM with the label 'VIRTIO'. Please attach the 'virtio-win.iso' to the VM."
        
        logger.info(f"Found VirtIO ISO at drive: {drive_letter}")
        
        # 2. Construct installer path and run command
        # We target the 64-bit guest tools installer
        installer_path = f"{drive_letter}\\virtio-win-gt-x64.msi"
        
        logger.info(f"Executing installer in guest: {installer_path}")
        
        # Use guest-exec to run msiexec silently
        exec_cmd = {
            "execute": "guest-exec",
            "arguments": {
                "path": "C:\\Windows\\System32\\msiexec.exe",
                "arg": [
                    "/i",
                    installer_path,
                    "/qn", # Quiet mode, no UI
                    "/norestart" # Do not automatically restart
                ],
                "capture-output": True
            }
        }

        success, response = self._run_qemu_agent_command(vm_name, exec_cmd, timeout=30)
        
        if not success:
            return False, f"Failed to execute guest command: {response.get('error')}"

        if "return" not in response or "pid" not in response["return"]:
             # This can happen if the command failed immediately
             return False, f"Guest command failed. Is the path correct? {installer_path}"

        pid = response.get("return", {}).get("pid")
        logger.info(f"Guest tools installer started (PID: {pid}). Monitoring...")
        
        # 3. Wait for the installer to finish (short poll)
        # msiexec might return immediately, so we poll for its status.
        start_time = time.time()
        while time.time() - start_time < 120: # 2 minute timeout
            status_cmd = {"execute": "guest-exec-status", "arguments": {"pid": pid}}
            status_success, status_response = self._run_qemu_agent_command(vm_name, status_cmd)
            
            if status_success and status_response.get("return", {}).get("exited", False):
                exit_code = status_response["return"].get("exitcode", -1)
                if exit_code == 0:
                    logger.info("Guest tools installer finished successfully.")
                    return True, "VirtIO guest tools installed successfully."
                else:
                    logger.error(f"Guest tools installer failed with exit code: {exit_code}")
                    return False, f"Installer failed with exit code: {exit_code}. Check guest logs."
            
            time.sleep(2)
            
        return False, "Installer process timed out. It may be running in the background, or it may have failed."

    # --- End Task 1.4 ---

    def get_guest_os_info(self, vm_name: str) -> Optional[Dict]:
        """
        Get guest OS information via guest agent
        
        Args:
            vm_name: VM name
            
        Returns:
            Dictionary with OS info or None
        """
        success, response = self._run_qemu_agent_command(vm_name, {"execute":"guest-get-osinfo"})
        if success and "return" in response:
            os_info = response.get('return', {})
            logger.info(f"Guest OS: {os_info.get('name')} {os_info.get('version')}")
            return os_info
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
            
            success, response = self._run_qemu_agent_command(vm_name, exec_cmd, timeout=30)
            if not success:
                return False, response.get("error")

            pid = response.get('return', {}).get('pid')
            if not pid:
                return False, "No PID returned from guest-exec"
            
            logger.debug(f"Guest command started with PID {pid}")
            
            # Wait for command completion
            start_time = time.time()
            while time.time() - start_time < timeout:
                status_cmd = {
                    "execute": "guest-exec-status",
                    "arguments": {"pid": pid}
                }
                
                status_success, status_response = self._run_qemu_agent_command(vm_name, status_cmd)
                
                if status_success and "return" in status_response:
                    status_info = status_response.get('return', {})
                    
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
            return False, "Command timed out"
            
        except Exception as e:
            logger.error(f"Failed to execute guest command: {e}")
            return False, str(e)
    
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
            
            success, response = self._run_qemu_agent_command(vm_name, write_cmd, timeout=120)
            if success:
                logger.info("File copied successfully")
                return True
            else:
                logger.error(f"Failed to copy file to guest: {response.get('error')}")
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
            # Use the guest-agent reboot mode
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