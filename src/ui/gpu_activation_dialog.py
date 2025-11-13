"""
GPU Activation Dialog - Orchestrates two-stage GPU passthrough activation
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

from backend.gpu_detector import GPUDetector, GPU
from backend.guest_driver_helper import GuestDriverHelper
from backend.vm_gpu_configurator import VMGPUConfigurator
from backend.libvirt_manager import LibvirtManager
from utils.logger import logger


class GPUActivationWorker(QThread):
    """Worker thread for GPU activation process"""
    
    progress_updated = Signal(int, str)
    finished = Signal(bool, str)
    
    def __init__(self, vm_name: str, gpu: GPU):
        super().__init__()
        self.vm_name = vm_name
        self.gpu = gpu
        self.manager = LibvirtManager()
        self.helper = GuestDriverHelper(self.manager)
        self.configurator = VMGPUConfigurator(self.manager)
    
    def run(self):
        """Run GPU activation workflow"""
        try:
            # Stage 1: Enable GPU passthrough
            self.progress_updated.emit(20, "Stopping VM if running...")
            
            self.progress_updated.emit(40, "Binding GPU to VFIO driver...")
            
            if not self.configurator.enable_gpu_passthrough(self.vm_name, self.gpu):
                self.finished.emit(False, "Failed to enable GPU passthrough. Check logs for details.")
                return
            
            self.progress_updated.emit(80, "Updating VM configuration...")
            
            # Stage 2: Success
            self.progress_updated.emit(100, "GPU passthrough enabled successfully!")
            self.finished.emit(
                True,
                f"GPU passthrough enabled!\n\n"
                f"Next steps:\n"
                f"1. Start the VM\n"
                f"2. Install NVIDIA/AMD drivers in Windows\n"
                f"3. Reboot Windows VM\n"
                f"4. Enjoy GPU acceleration!"
            )
            
        except Exception as e:
            logger.exception("GPU activation failed")
            self.finished.emit(False, f"Unexpected error: {str(e)}")
        finally:
            # Clean up libvirt connection
            try:
                self.manager.disconnect()
            except:
                pass


class GPUActivationDialog(QDialog):
    """Dialog for activating GPU passthrough after driver installation"""
    
    def __init__(self, vm_name: str, gpu: GPU, parent=None):
        super().__init__(parent)
        
        self.vm_name = vm_name
        self.gpu = gpu
        
        self.setWindowTitle(f"Activate GPU Passthrough - {vm_name}")
        self.setMinimumSize(600, 400)
        self.setModal(True)
        
        self._setup_ui()
        self._apply_theme()
    
    def _setup_ui(self):
        """Setup dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(f"GPU Passthrough Activation")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Info
        info = QLabel(
            f"VM: {self.vm_name}\n"
            f"GPU: {self.gpu.full_name} ({self.gpu.pci_address})\n\n"
            "This will:\n"
            "1. Verify VirtIO drivers are installed\n"
            "2. Download and install GPU drivers\n"
            "3. Enable GPU passthrough\n"
            "4. Reboot VM with GPU"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to start")
        layout.addWidget(self.status_label)
        
        # Log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        # Buttons
        self.start_btn = QPushButton("Start Activation")
        self.start_btn.clicked.connect(self._start_activation)
        layout.addWidget(self.start_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        self.close_btn.setEnabled(False)
        layout.addWidget(self.close_btn)
    
    def _apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QProgressBar {
                border: 2px solid #3E3E3E;
                border-radius: 5px;
                text-align: center;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                background-color: #0D7377;
            }
            QTextEdit {
                background-color: #2B2B2B;
                border: 1px solid #3E3E3E;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #0D7377;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
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
    
    def _start_activation(self):
        """Start GPU activation process"""
        self.start_btn.setEnabled(False)
        self.log_text.append("Starting GPU activation...\n")
        
        # Create worker thread
        self.worker = GPUActivationWorker(self.vm_name, self.gpu)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
    
    def _on_progress(self, value: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        self.log_text.append(f"[{value}%] {message}")
    
    def _on_finished(self, success: bool, message: str):
        """Handle completion"""
        self.close_btn.setEnabled(True)
        
        if success:
            self.log_text.append(f"\n✓ SUCCESS: {message}")
            QMessageBox.information(
                self,
                "Success",
                f"GPU passthrough activated successfully!\n\n"
                f"VM '{self.vm_name}' now has access to {self.gpu.full_name}"
            )
        else:
            self.log_text.append(f"\n✗ FAILED: {message}")
            QMessageBox.critical(
                self,
                "Failed",
                f"GPU activation failed:\n{message}"
            )
