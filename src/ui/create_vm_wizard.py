"""
VM Creation Wizard - Multi-step interface for creating Windows VMs
"""

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton, QFileDialog,
    QCheckBox, QComboBox, QGroupBox, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from typing import Optional
from pathlib import Path

from backend.gpu_detector import GPUDetector, GPU
from backend.xml_generator import XMLGenerator
from backend.libvirt_manager import LibvirtManager
from models.gpu_model import GPUModel
from utils.logger import logger
import config


class IntroPage(QWizardPage):
    """Introduction page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Create New Windows VM")
        self.setSubTitle("This wizard will guide you through creating a Windows 10/11 virtual machine with optional GPU passthrough.")
        
        layout = QVBoxLayout(self)
        
        info = QLabel(
            "VirtFlow will automate:\n\n"
            "• Windows ISO detection and boot\n"
            "• VirtIO driver installation\n"
            "• GPU passthrough configuration\n"
            "• Performance optimizations\n\n"
            "Click Next to begin."
        )
        info.setWordWrap(True)
        layout.addWidget(info)


class VMConfigPage(QWizardPage):
    """VM basic configuration page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("VM Configuration")
        self.setSubTitle("Configure basic VM settings")
        
        layout = QVBoxLayout(self)
        
        # VM Name
        name_group = QGroupBox("VM Name")
        name_layout = QVBoxLayout(name_group)
        self.name_input = QLineEdit("Windows10")
        name_layout.addWidget(self.name_input)
        layout.addWidget(name_group)
        
        # Memory
        memory_group = QGroupBox("Memory (RAM)")
        memory_layout = QHBoxLayout(memory_group)
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(2048, 65536)
        self.memory_spin.setValue(8192)
        self.memory_spin.setSingleStep(1024)
        self.memory_spin.setSuffix(" MB")
        memory_layout.addWidget(self.memory_spin)
        layout.addWidget(memory_group)
        
        # CPUs
        cpu_group = QGroupBox("Virtual CPUs")
        cpu_layout = QHBoxLayout(cpu_group)
        self.cpu_spin = QSpinBox()
        self.cpu_spin.setRange(1, 32)
        self.cpu_spin.setValue(4)
        cpu_layout.addWidget(self.cpu_spin)
        layout.addWidget(cpu_group)
        
        # Windows 11 TPM
        self.tpm_checkbox = QCheckBox("Enable TPM 2.0 (Required for Windows 11)")
        self.tpm_checkbox.setChecked(True)
        layout.addWidget(self.tpm_checkbox)
        
        # Register fields
        self.registerField("vm_name*", self.name_input)
        self.registerField("memory", self.memory_spin)
        self.registerField("vcpus", self.cpu_spin)
        self.registerField("enable_tpm", self.tpm_checkbox)


class StoragePage(QWizardPage):
    """Storage configuration page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Storage Configuration")
        self.setSubTitle("Select Windows ISO and configure disk")
        
        layout = QVBoxLayout(self)
        
        # Windows ISO
        iso_group = QGroupBox("Windows Installation ISO")
        iso_layout = QHBoxLayout(iso_group)
        self.iso_input = QLineEdit()
        iso_browse = QPushButton("Browse...")
        iso_browse.clicked.connect(self._browse_iso)
        iso_layout.addWidget(self.iso_input)
        iso_layout.addWidget(iso_browse)
        layout.addWidget(iso_group)
        
        # VirtIO ISO
        virtio_group = QGroupBox("VirtIO Drivers ISO")
        virtio_layout = QHBoxLayout(virtio_group)
        self.virtio_input = QLineEdit()
        virtio_browse = QPushButton("Browse...")
        virtio_browse.clicked.connect(self._browse_virtio)
        virtio_layout.addWidget(self.virtio_input)
        virtio_layout.addWidget(virtio_browse)
        layout.addWidget(virtio_group)
        
        # Disk size
        disk_group = QGroupBox("Virtual Disk Size")
        disk_layout = QHBoxLayout(disk_group)
        self.disk_spin = QSpinBox()
        self.disk_spin.setRange(20, 500)
        self.disk_spin.setValue(60)
        self.disk_spin.setSuffix(" GB")
        disk_layout.addWidget(self.disk_spin)
        layout.addWidget(disk_group)
        
        # Register fields
        self.registerField("iso_path*", self.iso_input)
        self.registerField("virtio_iso_path*", self.virtio_input)
        self.registerField("disk_size", self.disk_spin)
    
    def _browse_iso(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Windows ISO", str(Path.home()),
            "ISO Files (*.iso)"
        )
        if path:
            self.iso_input.setText(path)
    
    def _browse_virtio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select VirtIO ISO", str(Path.home()),
            "ISO Files (*.iso)"
        )
        if path:
            self.virtio_input.setText(path)


class GPUPage(QWizardPage):
    """GPU selection page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("GPU Passthrough")
        self.setSubTitle("Select GPU for passthrough (optional)")
        
        self.detector = GPUDetector()
        self.selected_gpu: Optional[GPU] = None
        
        layout = QVBoxLayout(self)
        
        # GPU selection
        gpu_group = QGroupBox("Available GPUs")
        gpu_layout = QVBoxLayout(gpu_group)
        
        self.gpu_combo = QComboBox()
        self._load_gpus()
        gpu_layout.addWidget(self.gpu_combo)
        
        self.gpu_info = QTextEdit()
        self.gpu_info.setReadOnly(True)
        self.gpu_info.setMaximumHeight(150)
        gpu_layout.addWidget(self.gpu_info)
        
        layout.addWidget(gpu_group)
        
        # Enable passthrough checkbox
        self.enable_passthrough = QCheckBox("Enable GPU Passthrough")
        self.enable_passthrough.stateChanged.connect(self._on_passthrough_toggled)
        layout.addWidget(self.enable_passthrough)
        
        # Warning
        warning = QLabel(
            "⚠ First boot will use basic graphics to install drivers.\n"
            "GPU passthrough will be enabled on subsequent boots."
        )
        warning.setStyleSheet("color: #FF9800;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        self.registerField("enable_gpu_passthrough", self.enable_passthrough)
    
    def _load_gpus(self):
        self.gpu_combo.clear()
        self.gpu_combo.addItem("No GPU Passthrough", None)
        
        for gpu in self.detector.get_passthrough_gpus():
            display_name = f"{gpu.full_name} ({gpu.pci_address})"
            self.gpu_combo.addItem(display_name, gpu)
    
    def _on_passthrough_toggled(self, state):
        self.gpu_combo.setEnabled(state == Qt.Checked)


class SummaryPage(QWizardPage):
    """Final summary page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Summary")
        self.setSubTitle("Review your VM configuration")
        
        layout = QVBoxLayout(self)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)
    
    def initializePage(self):
        """Generate summary when page is shown"""
        vm_name = self.field("vm_name")
        memory = self.field("memory")
        vcpus = self.field("vcpus")
        enable_tpm = self.field("enable_tpm")
        iso_path = self.field("iso_path")
        disk_size = self.field("disk_size")
        enable_gpu = self.field("enable_gpu_passthrough")
        
        summary = f"VM Configuration:\n\n"
        summary += f"Name: {vm_name}\n"
        summary += f"Memory: {memory} MB\n"
        summary += f"CPUs: {vcpus}\n"
        summary += f"TPM 2.0: {'Enabled' if enable_tpm else 'Disabled'}\n"
        summary += f"Disk Size: {disk_size} GB\n"
        summary += f"Windows ISO: {Path(iso_path).name}\n"
        summary += f"GPU Passthrough: {'Enabled' if enable_gpu else 'Disabled'}\n"
        
        self.summary_text.setPlainText(summary)


class CreateVMWizard(QWizard):
    """Main VM creation wizard"""
    
    vm_created = Signal(str)  # Emits VM name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Create Windows VM - VirtFlow")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(700, 500)
        
        # Add pages
        self.addPage(IntroPage())
        self.addPage(VMConfigPage())
        self.addPage(StoragePage())
        self.addPage(GPUPage())
        self.addPage(SummaryPage())
        
        # Setup
        self.xml_generator = XMLGenerator()
        self.manager = LibvirtManager()
        
        # Apply theme
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QWizard {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QWizardPage {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
            }
            QGroupBox {
                border: 2px solid #3E3E3E;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #2B2B2B;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
                padding: 5px;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #0D7377;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #14FFEC;
                color: #1E1E1E;
            }
            QTextEdit {
                background-color: #2B2B2B;
                border: 1px solid #3E3E3E;
                color: #FFFFFF;
            }
        """)
    
    def accept(self):
        """Create VM when wizard finishes"""
        try:
            logger.info("Creating VM from wizard...")
            
            # Get all fields
            vm_name = self.field("vm_name")
            memory = self.field("memory")
            vcpus = self.field("vcpus")
            enable_tpm = self.field("enable_tpm")
            iso_path = self.field("iso_path")
            virtio_iso = self.field("virtio_iso_path")
            disk_size = self.field("disk_size")
            enable_gpu = self.field("enable_gpu_passthrough")
            
            # Validate inputs
            if not vm_name or len(vm_name.strip()) == 0:
                QMessageBox.critical(self, "Error", "VM name cannot be empty")
                return
            
            if not Path(iso_path).exists():
                QMessageBox.critical(self, "Error", f"Windows ISO not found: {iso_path}")
                return
            
            if not Path(virtio_iso).exists():
                QMessageBox.critical(self, "Error", f"VirtIO ISO not found: {virtio_iso}")
                return
            
            # Use DiskManager for disk creation
            from backend.disk_manager import DiskManager
            disk_mgr = DiskManager()
            
            # Create disk image
            disk_path = disk_mgr.get_disk_path(vm_name)
            
            if Path(disk_path).exists():
                reply = QMessageBox.question(
                    self,
                    "Disk Exists",
                    f"Disk already exists: {disk_path}\nOverwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
                disk_mgr.delete_disk(disk_path)
            
            logger.info(f"Creating disk: {disk_path} ({disk_size}GB)")
            if not disk_mgr.create_disk_image(disk_path, disk_size):
                QMessageBox.critical(
                    self,
                    "Disk Creation Failed",
                    f"Failed to create disk image.\n\n"
                    f"Check that qemu-img is installed and you have write permissions to:\n"
                    f"{disk_path}"
                )
                return
            
            # Generate XML (without GPU for first boot)
            from backend.xml_generator import XMLGenerator
            xml_gen = XMLGenerator()
            
            xml = xml_gen.generate_windows_vm_xml(
                vm_name=vm_name,
                memory_mb=memory,
                vcpus=vcpus,
                disk_path=disk_path,
                iso_path=iso_path,
                virtio_iso_path=virtio_iso,
                gpu=None,  # No GPU on first boot
                enable_tpm=enable_tpm,
                enable_gpu_passthrough=False
            )
            
            # Create VM
            domain = self.manager.create_vm_from_xml(xml)
            
            if domain:
                reply = QMessageBox.question(
                    self,
                    "VM Created",
                    f"VM '{vm_name}' created successfully!\n\n"
                    f"Would you like to start it now?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    from backend.vm_controller import VMController
                    controller = VMController(self.manager)
                    controller.start_vm_with_viewer(domain, fullscreen=False)

                self.vm_created.emit(vm_name)
                super().accept()
            else:
                QMessageBox.critical(
                    self,
                    "VM Creation Failed",
                    "Failed to create VM. Check libvirt logs for details."
                )
                # Cleanup disk if VM creation failed
                disk_mgr.delete_disk(disk_path)
            
        except Exception as e:
            logger.exception("Failed to create VM")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create VM:\n\n{str(e)}\n\n"
                "Check the logs for more details."
            )
    
    def _create_disk_image(self, path: str, size_gb: int):
        """Create qcow2 disk image"""
        import subprocess
        
        cmd = [
            'qemu-img', 'create',
            '-f', 'qcow2',
            path,
            f'{size_gb}G'
        ]
        
        subprocess.run(cmd, check=True)
        logger.info(f"Created disk image: {path} ({size_gb}GB)")
