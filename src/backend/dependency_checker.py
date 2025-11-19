"""
Checks for all required system dependencies for The Wolf VM.
"""
import shutil
import subprocess
from utils.logger import logger

# --- Required Binaries ---
REQUIRED_BINARIES = [
    'qemu-system-x86_64',   # Core Hypervisor
    'virsh',                # Libvirt Management
    'virt-viewer',          # SPICE Display
    'looking-glass-client', # High-Performance Display
    'xdotool',              # Window Management (for LG resizing)
    'wmctrl'                # Window Management (for LG positioning)
]

REQUIRED_PACKAGES = {
    'debian': [
        'qemu-system-x86', 
        'qemu-kvm', 
        'libvirt-daemon-system', 
        'libvirt-clients', 
        'bridge-utils', 
        'virt-manager',
        'ovmf',
        'looking-glass-client', 
        'xdotool',              
        'wmctrl'                
    ],
    'redhat': [
        'qemu-kvm', 
        'libvirt-daemon', 
        'libvirt-client', 
        'bridge-utils', 
        'virt-install',
        'ovmf',
        'looking-glass-client', 
        'xdotool',              
        'wmctrl'                
    ],
}

REQUIRED_GROUPS = ['libvirt', 'kvm']

class DependencyChecker:
    """Checks for system dependencies"""
    
    def __init__(self):
        self.distro = self._detect_distro()

    def _detect_distro(self) -> str:
        """Detect Linux distribution"""
        try:
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith('ID_LIKE='):
                        if 'debian' in line:
                            return 'debian'
                        if 'fedora' in line or 'rhel' in line:
                            return 'redhat'
                    if line.startswith('ID='):
                        if 'debian' in line or 'ubuntu' in line:
                            return 'debian'
                        if 'fedora' in line or 'rhel' in line or 'centos' in line:
                            return 'redhat'
        except FileNotFoundError:
            logger.warning("Could not detect distro, assuming debian-like")
            return 'debian'
        return 'debian'

    def check_all_dependencies(self) -> (bool, list):
        """Check for all required binaries"""
        missing = []
        for binary in REQUIRED_BINARIES:
            if not shutil.which(binary):
                logger.warning(f"Missing dependency: {binary}")
                missing.append(binary)
        
        if missing:
            return False, missing
        
        logger.info("All binary dependencies are satisfied")
        return True, []

    def get_install_command(self, missing_binaries: list) -> str:
        """Get install command for missing packages"""
        if not self.distro:
            return "Could not detect distro. Please install manually."
        
        packages = REQUIRED_PACKAGES.get(self.distro, [])
        if not packages:
            return "Distro not supported for automatic package suggestions."
            
        if self.distro == 'debian':
            return f"sudo apt install -y {' '.join(packages)}"
        elif self.distro == 'redhat':
            return f"sudo dnf install -y {' '.join(packages)}"
        
        return "Please install missing packages manually."

    def check_user_groups(self) -> (bool, list):
        """Check if user is in required groups"""
        missing_groups = []
        try:
            result = subprocess.run(['id', '-Gn'], capture_output=True, text=True, check=True)
            current_groups = result.stdout.strip().split()
            
            for group in REQUIRED_GROUPS:
                if group not in current_groups:
                    logger.warning(f"User not in group: {group}")
                    missing_groups.append(group)
            
            if missing_groups:
                return False, missing_groups
            
            logger.info("User is in all required groups")
            return True, []
            
        except Exception as e:
            logger.error(f"Failed to check user groups: {e}")
            return False, REQUIRED_GROUPS

    def check_libvirt_connection(self) -> bool:
        """Check if libvirt daemon is running and accessible"""
        try:
            result = subprocess.run(
                ['virsh', 'uri'], 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=5
            )
            if 'qemu:///system' in result.stdout:
                logger.info("libvirt daemon is accessible")
                return True
            else:
                logger.warning("libvirt daemon not accessible")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to libvirt: {e}")
            return False