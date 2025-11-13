"""
Disk Manager - Handles VM disk creation with proper permissions
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from utils.logger import logger


class DiskManager:
    """Manages VM disk images"""
    
    def __init__(self):
        # Use user's home directory for disk images (not /var/lib/libvirt/images)
        self.default_disk_dir = Path.home() / ".local" / "share" / "virtflow" / "disks"
        self.default_disk_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Disk directory: {self.default_disk_dir}")
    
    def get_disk_path(self, vm_name: str) -> str:
        """
        Get disk path for a VM
        
        Args:
            vm_name: VM name
            
        Returns:
            Full path to disk image
        """
        return str(self.default_disk_dir / f"{vm_name}.qcow2")
    
    def check_qemu_img_available(self) -> bool:
        """Check if qemu-img is available"""
        try:
            result = subprocess.run(
                ['qemu-img', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"qemu-img found: {result.stdout.split()[0]}")
                return True
        except FileNotFoundError:
            logger.error("qemu-img not found in PATH")
        except Exception as e:
            logger.error(f"Failed to check qemu-img: {e}")
        
        return False
    
    def create_disk_image(
        self,
        path: str,
        size_gb: int,
        format: str = 'qcow2'
    ) -> bool:
        """
        Create a disk image
        
        Args:
            path: Full path to disk image
            size_gb: Size in GB
            format: Disk format (qcow2, raw, etc.)
            
        Returns:
            bool: Success status
        """
        if not self.check_qemu_img_available():
            logger.error("qemu-img not available")
            return False
        
        # Ensure parent directory exists
        disk_path = Path(path)
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if disk already exists
        if disk_path.exists():
            logger.warning(f"Disk already exists: {path}")
            return False
        
        logger.info(f"Creating {format} disk: {path} ({size_gb}GB)")
        
        try:
            cmd = [
                'qemu-img', 'create',
                '-f', format,
                path,
                f'{size_gb}G'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Disk created successfully: {path}")
                return True
            else:
                logger.error(f"qemu-img failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Disk creation timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to create disk: {e}")
            return False
    
    def get_disk_info(self, path: str) -> Optional[dict]:
        """
        Get disk image information
        
        Args:
            path: Path to disk image
            
        Returns:
            Dictionary with disk info or None
        """
        try:
            result = subprocess.run(
                ['qemu-img', 'info', '--output=json', path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to get disk info: {e}")
        
        return None
    
    def resize_disk(self, path: str, new_size_gb: int) -> bool:
        """Resize an existing disk image"""
        try:
            result = subprocess.run(
                ['qemu-img', 'resize', path, f'{new_size_gb}G'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to resize disk: {e}")
            return False
    
    def delete_disk(self, path: str) -> bool:
        """Delete a disk image"""
        try:
            disk_path = Path(path)
            if disk_path.exists():
                disk_path.unlink()
                logger.info(f"Deleted disk: {path}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete disk: {e}")
        
        return False
