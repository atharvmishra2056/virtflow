import re
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List


# Known PCI vendor IDs of GPUs
GPU_VENDORS = {
    '10de': 'NVIDIA',
    '1002': 'AMD',
    '8086': 'Intel'
}

VGA_CLASS_CODE = '0300'
DISPLAY_CLASS_CODE = '0380'


@dataclass
class PCIDevice:
    address: str
    vendor_id: str
    device_id: str
    class_code: str
    vendor_name: str
    device_name: str
    iommu_group: Optional[int] = None
    driver: Optional[str] = None
    
    def is_gpu(self) -> bool:
        return self.class_code in {VGA_CLASS_CODE, DISPLAY_CLASS_CODE}
    
    def is_integrated(self) -> bool:
        """
        More robust integrated GPU detection, especially for AMD GPUs:
        - Integrated GPU usually on PCI bus 0 (bus number after domain)
        - For AMD, check if device name contains 'APU' or 'Integrated'
        """
        # Extract bus number
        try:
            bus = int(self.address.split(':')[1], 16)
        except Exception:
            bus = -1
        
        if self.vendor_id == '8086':  # Intel usually integrated
            return True
        
        if self.vendor_id == '1002':  # AMD - check bus and name heuristics
            if bus == 0:
                return True
            lower_name = self.device_name.lower()
            if 'apu' in lower_name or 'integrated' in lower_name:
                return True
        
        return False


def get_iommu_group(pci_address: str) -> Optional[int]:
    try:
        iommu_path = Path(f'/sys/bus/pci/devices/{pci_address}/iommu_group')
        if iommu_path.exists() and iommu_path.is_symlink():
            link = iommu_path.resolve()
            return int(link.name)
    except Exception:
        pass
    return None


def get_driver(pci_address: str) -> Optional[str]:
    try:
        driver_path = Path(f'/sys/bus/pci/devices/{pci_address}/driver')
        if driver_path.exists() and driver_path.is_symlink():
            driver_name = driver_path.resolve().name
            return driver_name
    except Exception:
        pass
    return None


def is_boot_vga(pci_address: str) -> bool:
    try:
        boot_vga_path = Path(f'/sys/bus/pci/devices/{pci_address}/boot_vga')
        if boot_vga_path.exists() and boot_vga_path.read_text().strip() == '1':
            return True
    except Exception:
        pass
    return False


def parse_lspci() -> List[PCIDevice]:
    result = subprocess.run(['lspci', '-nn', '-D'], capture_output=True, text=True)
    devices = []
    for line in result.stdout.strip().split('\n'):
        m_address = re.match(r'([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.\d)\s', line)
        if not m_address:
            continue
        address = m_address.group(1)
        m_info = re.search(r'\[(\w{4})\]:.*\[(\w{4}):(\w{4})\]', line)
        if not m_info:
            continue
        class_code, vendor_id, device_id = m_info.groups()
        name_match = re.search(r': (.+) \[', line)
        device_name = name_match.group(1) if name_match else "Unknown Device"
        vendor_name = GPU_VENDORS.get(vendor_id, f"Vendor {vendor_id}")
        
        iommu_group = get_iommu_group(address)
        driver = get_driver(address)
        
        device = PCIDevice(
            address=address,
            vendor_id=vendor_id,
            device_id=device_id,
            class_code=class_code,
            vendor_name=vendor_name,
            device_name=device_name,
            iommu_group=iommu_group,
            driver=driver
        )
        devices.append(device)
    return devices


def detect_gpus(devices: List[PCIDevice]) -> List[PCIDevice]:
    gpus = [dev for dev in devices if dev.is_gpu()]
    return gpus


def classify_gpus(gpus: List[PCIDevice]):
    for gpu in gpus:
        inte = gpu.is_integrated()
        prim = is_boot_vga(gpu.address)
        print(f"{gpu.address} - {gpu.vendor_name} {gpu.device_name}")
        print(f"  Integrated: {inte}")
        print(f"  Primary (boot_vga=1): {prim}")
        print(f"  IOMMU Group: {gpu.iommu_group}")
        print(f"  Driver: {gpu.driver}")
        print("")


def main():
    devices = parse_lspci()
    gpus = detect_gpus(devices)
    
    if not gpus:
        print("No GPUs detected.")
        return
    
    print(f"Detected GPUs: {len(gpus)}")
    classify_gpus(gpus)


if __name__ == "__main__":
    main()
