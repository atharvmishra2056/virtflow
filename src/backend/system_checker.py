"""
System requirements checker for VirtFlow
"""

import os
import subprocess
from pathlib import Path
from utils.logger import logger


class SystemChecker:
    """Check system requirements and capabilities"""
    
    def is_libvirt_running(self) -> bool:
        """Check if libvirtd service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'libvirtd'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to check libvirtd status: {e}")
            return False
    
    def has_kvm_support(self) -> bool:
        """Check if KVM is available"""
        kvm_device = Path('/dev/kvm')
        if not kvm_device.exists():
            return False
        
        # Check if accessible
        return os.access(kvm_device, os.R_OK | os.W_OK)
    
    def has_iommu_enabled(self) -> bool:
        """Check if IOMMU is enabled"""
        iommu_groups = Path('/sys/kernel/iommu_groups')
        
        if not iommu_groups.exists():
            return False
        
        # Check if there are any IOMMU groups
        try:
            groups = list(iommu_groups.iterdir())
            return len(groups) > 0
        except Exception as e:
            logger.error(f"Failed to check IOMMU groups: {e}")
            return False
    
    def get_kvm_module(self) -> str:
        """Detect which KVM module is loaded (intel or amd)"""
        try:
            result = subprocess.run(
                ['lsmod'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'kvm_intel' in result.stdout:
                return 'kvm_intel'
            elif 'kvm_amd' in result.stdout:
                return 'kvm_amd'
            else:
                return 'unknown'
        except Exception as e:
            logger.error(f"Failed to detect KVM module: {e}")
            return 'unknown'
