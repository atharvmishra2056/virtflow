"""
GPU model for UI representation
"""

from dataclasses import dataclass
from typing import List


@dataclass
class GPUModel:
    """UI-friendly GPU model"""
    
    pci_address: str
    vendor: str  # NVIDIA, AMD, Intel
    model: str
    iommu_group: int
    is_primary: bool
    can_passthrough: bool
    driver: str
    related_device_count: int
    
    @property
    def display_name(self) -> str:
        """Get display-friendly name"""
        primary_badge = " [Primary]" if self.is_primary else ""
        return f"{self.vendor} {self.model}{primary_badge}"
    
    @property
    def status_text(self) -> str:
        """Get status description"""
        if not self.can_passthrough:
            if self.is_primary:
                return "Cannot passthrough (Primary Display)"
            else:
                return "Passthrough unavailable"
        return "Available for passthrough"
    
    @property
    def status_color(self) -> str:
        """Get color for status"""
        if self.can_passthrough:
            return "#4CAF50"  # Green
        elif self.is_primary:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red
