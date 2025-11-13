"""
GPU Detection and IOMMU Group Analysis
Automatically detects GPUs, identifies vendors, and prepares for passthrough
"""

import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from utils.logger import logger


# PCI Vendor IDs for GPU manufacturers
GPU_VENDORS = {
    '10de': 'NVIDIA',
    '1002': 'AMD',
    '8086': 'Intel',
    '1a03': 'ASPEED',  # BMC graphics (server management)
    '102b': 'Matrox'
}

# PCI Class codes for display/VGA devices
VGA_CLASS_CODE = '0300'  # VGA compatible controller
DISPLAY_CLASS_CODE = '0380'  # Display controller
AUDIO_CLASS_CODE = '0403'  # Audio device (often paired with GPU)


@dataclass
class PCIDevice:
    """Represents a PCI device"""
    address: str  # e.g., "0000:01:00.0"
    vendor_id: str  # e.g., "10de"
    device_id: str  # e.g., "1c03"
    class_code: str  # e.g., "0300"
    vendor_name: str
    device_name: str
    iommu_group: Optional[int] = None
    driver: Optional[str] = None
    
    @property
    def is_gpu(self) -> bool:
        """Check if device is a GPU"""
        return self.class_code in [VGA_CLASS_CODE, DISPLAY_CLASS_CODE]
    
    @property
    def is_audio(self) -> bool:
        """Check if device is audio (often GPU HDMI audio)"""
        return self.class_code == AUDIO_CLASS_CODE
    
    @property
    def virsh_format(self) -> str:
        """Convert PCI address to virsh nodedev format"""
        # 0000:01:00.0 -> pci_0000_01_00_0
        return 'pci_' + self.address.replace(':', '_').replace('.', '_')


@dataclass
class GPU:
    """Represents a detected GPU with metadata"""
    pci_device: PCIDevice
    vendor: str  # NVIDIA, AMD, Intel
    model: str
    iommu_group: int
    related_devices: List[PCIDevice]  # Audio, USB controllers, etc.
    is_primary: bool = False  # Connected to display output
    can_passthrough: bool = True
    
    @property
    def full_name(self) -> str:
        """Get full GPU name"""
        return f"{self.vendor} {self.model}"
    
    @property
    def pci_address(self) -> str:
        """Get PCI address"""
        return self.pci_device.address
    
    @property
    def all_devices(self) -> List[PCIDevice]:
        """Get GPU + all related devices"""
        return [self.pci_device] + self.related_devices


class GPUDetector:
    """Detects and analyzes GPUs for passthrough"""
    
    def __init__(self):
        self.gpus: List[GPU] = []
        self.all_pci_devices: List[PCIDevice] = []
        self.iommu_enabled = False
        self._scan_system()
    
    def _scan_system(self):
        """Scan system for GPUs and IOMMU configuration"""
        logger.info("Starting GPU detection scan...")
        
        # Check IOMMU
        self.iommu_enabled = self._check_iommu()
        
        # Scan PCI devices
        self._scan_pci_devices()
        
        # Detect GPUs
        self._detect_gpus()
        
        # Analyze passthrough capability
        self._analyze_passthrough_capability()
        
        logger.info(f"GPU detection complete: Found {len(self.gpus)} GPU(s)")
    
    def _check_iommu(self) -> bool:
        """Check if IOMMU is enabled"""
        iommu_path = Path('/sys/kernel/iommu_groups')
        
        if not iommu_path.exists():
            logger.warning("IOMMU not enabled - GPU passthrough unavailable")
            return False
        
        # Count IOMMU groups
        try:
            groups = list(iommu_path.iterdir())
            logger.info(f"IOMMU enabled with {len(groups)} groups")
            return len(groups) > 0
        except Exception as e:
            logger.error(f"Failed to check IOMMU: {e}")
            return False
    
    def _scan_pci_devices(self):
        """Scan all PCI devices using lspci"""
        try:
            # Run lspci with numeric IDs and verbose output
            result = subprocess.run(
                ['lspci', '-nn', '-D'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            for line in result.stdout.strip().split('\n'):
                device = self._parse_lspci_line(line)
                if device:
                    # Add IOMMU group info
                    device.iommu_group = self._get_iommu_group(device.address)
                    # Add driver info
                    device.driver = self._get_device_driver(device.address)
                    self.all_pci_devices.append(device)
            
            logger.debug(f"Scanned {len(self.all_pci_devices)} PCI devices")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"lspci failed: {e}")
        except Exception as e:
            logger.error(f"Failed to scan PCI devices: {e}")
    
    def _parse_lspci_line(self, line: str) -> Optional[PCIDevice]:
        """
        Parse a single lspci output line
        Format: 0000:01:00.0 VGA compatible controller [0300]: NVIDIA Corporation [10de:1c03]
        """
        try:
            # Extract PCI address
            address_match = re.match(r'([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.\d+)', line)
            if not address_match:
                return None
            address = address_match.group(1)
            
            # Extract class, vendor:device IDs
            ids_match = re.search(r'\[([0-9a-f]{4})\]: .+\[([0-9a-f]{4}):([0-9a-f]{4})\]', line)
            if not ids_match:
                return None
            
            class_code = ids_match.group(1)
            vendor_id = ids_match.group(2)
            device_id = ids_match.group(3)
            
            # Extract device name (between ": " and " [")
            name_match = re.search(r': (.+?) \[', line)
            device_name = name_match.group(1) if name_match else "Unknown Device"
            
            # Get vendor name
            vendor_name = GPU_VENDORS.get(vendor_id, f"Vendor {vendor_id}")
            
            return PCIDevice(
                address=address,
                vendor_id=vendor_id,
                device_id=device_id,
                class_code=class_code,
                vendor_name=vendor_name,
                device_name=device_name
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse lspci line: {line} - {e}")
            return None
    
    def _get_iommu_group(self, pci_address: str) -> Optional[int]:
        """Get IOMMU group number for a PCI device"""
        try:
            # /sys/bus/pci/devices/0000:01:00.0/iommu_group -> ../../kernel/iommu_groups/1
            device_path = Path(f'/sys/bus/pci/devices/{pci_address}/iommu_group')
            
            if device_path.exists() and device_path.is_symlink():
                # Read symlink and extract group number
                link_target = device_path.resolve()
                group_num = int(link_target.name)
                return group_num
        except Exception as e:
            logger.debug(f"Could not get IOMMU group for {pci_address}: {e}")
        
        return None
    
    def _get_device_driver(self, pci_address: str) -> Optional[str]:
        """Get current driver for a PCI device"""
        try:
            driver_path = Path(f'/sys/bus/pci/devices/{pci_address}/driver')
            
            if driver_path.exists() and driver_path.is_symlink():
                # Read symlink to get driver name
                driver_name = driver_path.resolve().name
                return driver_name
        except Exception as e:
            logger.debug(f"Could not get driver for {pci_address}: {e}")
        
        return None
    
    def _detect_gpus(self):
        """Detect all GPUs from scanned PCI devices"""
        gpu_devices = [dev for dev in self.all_pci_devices if dev.is_gpu]
        
        for gpu_dev in gpu_devices:
            # Get vendor from vendor_id
            vendor = GPU_VENDORS.get(gpu_dev.vendor_id, "Unknown")
            
            # Find related devices in same IOMMU group (audio, USB, etc.)
            related = self._find_related_devices(gpu_dev)
            
            # Check if primary GPU (heuristic: IOMMU group 1 or using kernel driver)
            is_primary = self._is_primary_gpu(gpu_dev)
            
            gpu = GPU(
                pci_device=gpu_dev,
                vendor=vendor,
                model=gpu_dev.device_name,
                iommu_group=gpu_dev.iommu_group or -1,
                related_devices=related,
                is_primary=is_primary
            )
            
            self.gpus.append(gpu)
            logger.info(f"Detected GPU: {gpu.full_name} at {gpu.pci_address} "
                       f"(IOMMU Group {gpu.iommu_group}, Primary: {is_primary})")
    
    def _find_related_devices(self, gpu_device: PCIDevice) -> List[PCIDevice]:
        """Find devices related to GPU (audio, USB) in same IOMMU group"""
        if gpu_device.iommu_group is None:
            return []
        
        related = []
        for dev in self.all_pci_devices:
            if dev.address == gpu_device.address:
                continue  # Skip the GPU itself
            
            # Same IOMMU group and nearby PCI address suggests related device
            if dev.iommu_group == gpu_device.iommu_group:
                # Check if same bus (first 3 parts of address match)
                gpu_bus = ':'.join(gpu_device.address.split(':')[:2])
                dev_bus = ':'.join(dev.address.split(':')[:2])
                
                if gpu_bus == dev_bus:
                    related.append(dev)
                    logger.debug(f"Found related device: {dev.device_name} at {dev.address}")
        
        return related
    
    def _is_primary_gpu(self, gpu_device: PCIDevice) -> bool:
        """
        Heuristic to detect if GPU is primary (connected to display)
        - Using a display driver (not vfio-pci)
        - Early IOMMU group number
        - Boot VGA flag in sysfs
        """
        # Check boot_vga flag
        try:
            boot_vga_path = Path(f'/sys/bus/pci/devices/{gpu_device.address}/boot_vga')
            if boot_vga_path.exists():
                boot_vga = boot_vga_path.read_text().strip()
                if boot_vga == '1':
                    return True
        except:
            pass
        
        # Check if using native driver (not vfio-pci or stub)
        if gpu_device.driver and gpu_device.driver not in ['vfio-pci', 'pci-stub', None]:
            return True
        
        return False
    
    def _analyze_passthrough_capability(self):
        """Analyze which GPUs can be safely passed through"""
        if not self.iommu_enabled:
            for gpu in self.gpus:
                gpu.can_passthrough = False
            logger.warning("No GPU can be passed through - IOMMU disabled")
            return
        
        # Count non-primary GPUs
        secondary_gpus = [gpu for gpu in self.gpus if not gpu.is_primary]
        
        if len(self.gpus) == 1:
            # Only one GPU - cannot passthrough (would lose host display)
            self.gpus[0].can_passthrough = False
            logger.warning("Only 1 GPU detected - passthrough disabled to protect host display")
        elif len(secondary_gpus) == 0:
            # All GPUs marked primary (shouldn't happen, but safe fallback)
            logger.warning("All GPUs detected as primary - passthrough risky")
        else:
            # Mark non-primary GPUs as passthrough-capable
            for gpu in secondary_gpus:
                gpu.can_passthrough = True
                logger.info(f"GPU {gpu.full_name} marked for passthrough")
    
    def get_passthrough_gpus(self) -> List[GPU]:
        """Get list of GPUs available for passthrough"""
        return [gpu for gpu in self.gpus if gpu.can_passthrough]
    
    def get_primary_gpu(self) -> Optional[GPU]:
        """Get the primary GPU (host display)"""
        primary = [gpu for gpu in self.gpus if gpu.is_primary]
        return primary[0] if primary else None
    
    def get_gpu_by_address(self, pci_address: str) -> Optional[GPU]:
        """Get GPU by PCI address"""
        for gpu in self.gpus:
            if gpu.pci_address == pci_address:
                return gpu
        return None
