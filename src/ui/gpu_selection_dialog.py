"""
GPU Selection Dialog for VM Creation
Displays available GPUs and allows user to select for passthrough
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from backend.gpu_detector import GPUDetector, GPU
from models.gpu_model import GPUModel
from utils.logger import logger


class GPUSelectionDialog(QDialog):
    """Dialog for selecting GPU for passthrough"""
    
    gpu_selected = Signal(str)  # Emits PCI address
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Select GPU for Passthrough")
        self.setMinimumSize(700, 500)
        
        # Initialize GPU detector
        self.detector = GPUDetector()
        self.selected_gpu: Optional[GPU] = None
        
        self._setup_ui()
        self._load_gpus()
    
    def _setup_ui(self):
        """Setup dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("GPU Passthrough Configuration")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # System status
        self.status_group = QGroupBox("System Status")
        status_layout = QVBoxLayout(self.status_group)
        
        iommu_status = "✓ Enabled" if self.detector.iommu_enabled else "✗ Disabled"
        iommu_color = "#4CAF50" if self.detector.iommu_enabled else "#F44336"
        
        self.iommu_label = QLabel(f"IOMMU: {iommu_status}")
        self.iommu_label.setStyleSheet(f"color: {iommu_color}; font-weight: bold;")
        status_layout.addWidget(self.iommu_label)
        
        gpu_count = len(self.detector.gpus)
        passthrough_count = len(self.detector.get_passthrough_gpus())
        
        self.gpu_count_label = QLabel(
            f"Total GPUs: {gpu_count} | Available for passthrough: {passthrough_count}"
        )
        status_layout.addWidget(self.gpu_count_label)
        
        layout.addWidget(self.status_group)
        
        # GPU list
        gpu_group = QGroupBox("Available GPUs")
        gpu_layout = QVBoxLayout(gpu_group)
        
        self.gpu_list = QListWidget()
        self.gpu_list.setSelectionMode(QListWidget.SingleSelection)
        self.gpu_list.itemClicked.connect(self._on_gpu_selected)
        gpu_layout.addWidget(self.gpu_list)
        
        layout.addWidget(gpu_group)
        
        # GPU details
        details_group = QGroupBox("GPU Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.select_btn = QPushButton("Select GPU")
        self.select_btn.setEnabled(False)
        self.select_btn.clicked.connect(self._on_confirm)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.select_btn)
        
        layout.addLayout(button_layout)
        
        # Apply dark theme
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QGroupBox {
                border: 2px solid #3E3E3E;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 5px;
            }
            QListWidget {
                background-color: #2B2B2B;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #3E3E3E;
            }
            QListWidget::item:selected {
                background-color: #0D7377;
            }
            QTextEdit {
                background-color: #2B2B2B;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #0D7377;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14FFEC;
                color: #1E1E1E;
            }
            QPushButton:disabled {
                background-color: #3E3E3E;
                color: #666666;
            }
        """)
    
    def _load_gpus(self):
        """Load detected GPUs into list"""
        self.gpu_list.clear()
        
        if not self.detector.iommu_enabled:
            item = QListWidgetItem("⚠ IOMMU not enabled - GPU passthrough unavailable")
            item.setForeground(QColor("#F44336"))
            self.gpu_list.addItem(item)
            return
        
        if len(self.detector.gpus) == 0:
            item = QListWidgetItem("No GPUs detected")
            self.gpu_list.addItem(item)
            return
        
        for gpu in self.detector.gpus:
            gpu_model = GPUModel(
                pci_address=gpu.pci_address,
                vendor=gpu.vendor,
                model=gpu.model,
                iommu_group=gpu.iommu_group,
                is_primary=gpu.is_primary,
                can_passthrough=gpu.can_passthrough,
                driver=gpu.pci_device.driver or "None",
                related_device_count=len(gpu.related_devices)
            )
            
            # Create list item
            item_text = f"{gpu_model.display_name}\n" \
                       f"   {gpu.pci_address} | IOMMU Group {gpu.iommu_group} | {gpu_model.status_text}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, gpu)  # Store GPU object
            
            # Color code based on availability
            if gpu.can_passthrough:
                item.setForeground(QColor("#4CAF50"))  # Green
            elif gpu.is_primary:
                item.setForeground(QColor("#FF9800"))  # Orange
            else:
                item.setForeground(QColor("#9E9E9E"))  # Gray
            
            if not gpu.can_passthrough:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            
            self.gpu_list.addItem(item)
    
    def _on_gpu_selected(self, item: QListWidgetItem):
        """Handle GPU selection"""
        gpu = item.data(Qt.UserRole)
        
        if not isinstance(gpu, GPU):
            return
        
        self.selected_gpu = gpu
        self.select_btn.setEnabled(gpu.can_passthrough)
        
        # Show GPU details
        details = f"GPU: {gpu.full_name}\n"
        details += f"PCI Address: {gpu.pci_address}\n"
        details += f"Vendor ID: {gpu.pci_device.vendor_id}:{gpu.pci_device.device_id}\n"
        details += f"IOMMU Group: {gpu.iommu_group}\n"
        details += f"Current Driver: {gpu.pci_device.driver or 'None'}\n"
        details += f"Primary Display: {'Yes' if gpu.is_primary else 'No'}\n"
        details += f"Can Passthrough: {'Yes' if gpu.can_passthrough else 'No'}\n"
        details += f"\nRelated Devices ({len(gpu.related_devices)}):\n"
        
        for dev in gpu.related_devices:
            details += f"  - {dev.device_name} ({dev.address})\n"
        
        self.details_text.setPlainText(details)
    
    def _on_confirm(self):
        """Handle confirm button"""
        if not self.selected_gpu:
            return
        
        if not self.selected_gpu.can_passthrough:
            QMessageBox.warning(
                self,
                "Cannot Passthrough",
                f"GPU {self.selected_gpu.full_name} cannot be passed through.\n\n"
                f"Reason: {self._get_passthrough_blocked_reason()}"
            )
            return
        
        self.gpu_selected.emit(self.selected_gpu.pci_address)
        self.accept()
    
    def _get_passthrough_blocked_reason(self) -> str:
        """Get reason why passthrough is blocked"""
        if not self.detector.iommu_enabled:
            return "IOMMU is not enabled in BIOS/kernel"
        
        if self.selected_gpu and self.selected_gpu.is_primary:
            return "This is the primary display GPU"
        
        if len(self.detector.gpus) == 1:
            return "System has only one GPU (passthrough would break host display)"
        
        return "Unknown reason"
    
    def get_selected_gpu(self) -> Optional[GPU]:
        """Get the selected GPU"""
        return self.selected_gpu
