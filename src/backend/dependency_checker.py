"""
Dependency Checker - Verifies all required system packages are installed
"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
from utils.logger import logger


class DependencyChecker:
    """Check system dependencies"""
    
    REQUIRED_PACKAGES = {
        'qemu-img': 'qemu-utils',
        'virsh': 'libvirt-clients',
        'qemu-system-x86_64': 'qemu-system-x86',
        'lspci': 'pciutils',
        'lsmod': 'kmod',
        'virt-viewer': 'virt-viewer'
    }
    
    def check_all_dependencies(self) -> Tuple[bool, List[str]]:
        """
        Check all required dependencies
        
        Returns:
            Tuple of (all_ok, missing_packages)
        """
        missing = []
        
        for binary, package in self.REQUIRED_PACKAGES.items():
            if not self.check_binary(binary):
                missing.append(package)
                logger.warning(f"Missing: {binary} (install {package})")
        
        if not self.check_ovmf_installed():
            missing.append('ovmf')
            logger.warning("Missing OVMF firmware files (install ovmf)")

        all_ok = len(missing) == 0
        return all_ok, missing
    
    def check_binary(self, name: str) -> bool:
        """Check if a binary is available in PATH"""
        return shutil.which(name) is not None
    
    def get_install_command(self, packages: List[str]) -> str:
        """Get installation command for missing packages"""
        return f"sudo apt install -y {' '.join(packages)}"
    
    def check_libvirt_connection(self) -> bool:
        """Check if we can connect to libvirt"""
        try:
            result = subprocess.run(
                ['virsh', 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def check_user_groups(self) -> Tuple[bool, List[str]]:
        """Check if user is in required groups"""
        import os
        import grp
        
        required_groups = ['libvirt', 'kvm']
        user = os.getenv('USER')
        missing_groups = []
        
        try:
            user_groups = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
            
            for group in required_groups:
                if group not in user_groups:
                    missing_groups.append(group)
                    logger.warning(f"User not in group: {group}")
        except Exception as e:
            logger.error(f"Failed to check user groups: {e}")
        
        return len(missing_groups) == 0, missing_groups

    def check_ovmf_installed(self) -> bool:
        """Check if OVMF firmware is installed"""
        templates = [
            "/usr/share/OVMF/OVMF_CODE_4M.ms.fd",
            "/usr/share/OVMF/OVMF_CODE_4M.fd",
            "/usr/share/OVMF/OVMF_CODE.fd",
            "/usr/share/OVMF/OVMF_VARS_4M.ms.fd",
            "/usr/share/OVMF/OVMF_VARS_4M.fd",
            "/usr/share/OVMF/OVMF_VARS.fd",
        ]
        for f in templates:
            if Path(f).exists():
                return True
        return False

    def check_viewer_available(self) -> bool:
        """Check if SPICE/VNC viewer is available"""
        import shutil
        return shutil.which('virt-viewer') is not None or shutil.which('remote-viewer') is not None
