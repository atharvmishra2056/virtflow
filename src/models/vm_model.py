"""
VM data model for UI representation
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VMModel:
    """Data model for a virtual machine"""
    
    name: str
    uuid: str
    state: int
    state_name: str
    is_active: bool
    is_persistent: bool
    max_memory_mb: int
    current_memory_mb: int
    vcpus: int
    autostart: bool
    has_gpu_passthrough: bool = False
    gpu_vendor: Optional[str] = None
    
    # --- ADD THESE 4 LINES ---
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    net_rx_bytes: int = 0
    net_tx_bytes: int = 0
    
    @property
    def memory_gb(self) -> float:
        """Get current memory in GB"""
        return self.current_memory_mb / 1024
    
    @property
    def max_memory_gb(self) -> float:
        """Get max memory in GB"""
        return self.max_memory_mb / 1024
    
    @classmethod
    def from_libvirt_info(cls, info: dict):
        """Create VMModel from libvirt info dictionary"""
        return cls(
            name=info['name'],
            uuid=info['uuid'],
            state=info['state'],
            state_name=info['state_name'],
            is_active=info['is_active'],
            is_persistent=info['is_persistent'],
            max_memory_mb=info['max_memory'] // 1024,
            current_memory_mb=info['memory'] // 1024,
            vcpus=info['vcpus'],
            autostart=info['autostart'],
            # --- ADD THESE 4 LINES (with .get() for safety) ---
            disk_read_bytes=info.get('disk_read_bytes', 0),
            disk_write_bytes=info.get('disk_write_bytes', 0),
            net_rx_bytes=info.get('net_rx_bytes', 0),
            net_tx_bytes=info.get('net_tx_bytes', 0)
        )