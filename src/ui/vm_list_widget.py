"""
VM list table widget with real-time updates
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor

from backend.libvirt_manager import LibvirtManager
from backend.vm_controller import VMController, VMState
from models.vm_model import VMModel
from utils.logger import logger


class VMListWidget(QWidget):
    """Widget displaying list of VMs with controls"""
    
    vm_selected = Signal(str)  # Emits VM UUID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize backend
        self.manager = LibvirtManager()
        self.controller = VMController(self.manager)
        
        # Setup UI
        self._setup_ui()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_vm_list)
        self.refresh_timer.start(3000)  # Refresh every 3 seconds
        
        # Initial load
        self.refresh_vm_list()
    
    def _setup_ui(self):
        """Setup widget UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.clicked.connect(self._on_start_vm)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._on_stop_vm)
        
        self.reboot_btn = QPushButton("🔄 Reboot")
        self.reboot_btn.clicked.connect(self._on_reboot_vm)
        
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self._on_delete_vm)
        self.delete_btn.setStyleSheet("background-color: #C62828; color: white;")
        
        self.refresh_btn = QPushButton("↻ Refresh")
        self.refresh_btn.clicked.connect(self.refresh_vm_list)

        self.gpu_activate_btn = QPushButton("🎮 Activate GPU")
        self.gpu_activate_btn.clicked.connect(self._on_activate_gpu)
        
        self.looking_glass_btn = QPushButton("👁️ Setup Looking Glass")
        self.looking_glass_btn.clicked.connect(self._on_setup_looking_glass)
        
        self.install_lg_btn = QPushButton("📥 Install Looking Glass")
        self.install_lg_btn.clicked.connect(self._on_install_looking_glass)

        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.reboot_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.gpu_activate_btn)
        button_layout.addWidget(self.looking_glass_btn)
        button_layout.addWidget(self.install_lg_btn)
        button_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(button_layout)
        
        # VM table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Name", "State", "vCPUs", "Memory (GB)", "Autostart", "UUID"
        ])
        
        # Table styling
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
        layout.addWidget(self.table)
        
        # Apply dark theme to table
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2B2B2B;
                color: #FFFFFF;
                gridline-color: #3E3E3E;
                border: 1px solid #3E3E3E;
            }
            QTableWidget::item:selected {
                background-color: #0D7377;
            }
            QHeaderView::section {
                background-color: #1E1E1E;
                color: #FFFFFF;
                padding: 5px;
                border: 1px solid #3E3E3E;
            }
        """)
    
    def refresh_vm_list(self):
        """Refresh VM list from libvirt"""
        try:
            domains = self.manager.list_all_vms()
            
            # Clear table
            self.table.setRowCount(0)
            
            # Populate table
            for domain in domains:
                info = self.controller.get_vm_info(domain)
                if not info:
                    continue
                
                vm = VMModel.from_libvirt_info(info)
                self._add_vm_to_table(vm)
            
            logger.debug(f"Refreshed VM list: {len(domains)} VMs")
            
        except Exception as e:
            logger.error(f"Failed to refresh VM list: {e}")
    
    def _add_vm_to_table(self, vm: VMModel):
        """Add VM to table"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Name
        self.table.setItem(row, 0, QTableWidgetItem(vm.name))
        
        # State (with color coding)
        state_item = QTableWidgetItem(vm.state_name)
        if vm.is_active:
            state_item.setForeground(QColor("#4CAF50"))  # Green
        else:
            state_item.setForeground(QColor("#9E9E9E"))  # Gray
        self.table.setItem(row, 1, state_item)
        
        # vCPUs
        self.table.setItem(row, 2, QTableWidgetItem(str(vm.vcpus)))
        
        # Memory
        self.table.setItem(row, 3, QTableWidgetItem(f"{vm.memory_gb:.1f}"))
        
        # Autostart
        autostart = "Yes" if vm.autostart else "No"
        self.table.setItem(row, 4, QTableWidgetItem(autostart))
        
        # UUID
        self.table.setItem(row, 5, QTableWidgetItem(vm.uuid))
    
    def _get_selected_vm(self):
        """Get currently selected VM domain"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a VM first")
            return None
        
        row = selected[0].row()
        vm_name = self.table.item(row, 0).text()
        
        domain = self.manager.get_vm_by_name(vm_name)
        if not domain:
            QMessageBox.critical(self, "Error", f"VM '{vm_name}' not found")
        
        return domain
    
    def _on_start_vm(self):
        """Handle start VM button"""
        domain = self._get_selected_vm()
        if not domain:
            return
        
        vm_name = domain.name()
        
        # Disable button to prevent double-click
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Starting...")
        
        # Start VM in background thread to prevent UI freeze
        from PySide6.QtCore import QThread, Signal
        
        class VMStartWorker(QThread):
            finished = Signal(bool, str)
            
            def __init__(self, domain, vm_name):
                super().__init__()
                self.domain = domain
                self.vm_name = vm_name
            
            def run(self):
                try:
                    # Check if VM has GPU passthrough
                    xml_str = self.domain.XMLDesc(0)
                    has_gpu = '<hostdev' in xml_str and 'type=\'pci\'' in xml_str
                    
                    if has_gpu:
                        logger.info("VM has GPU passthrough, ensuring GPU is bound to VFIO...")
                        # Import here to avoid circular dependency
                        from backend.gpu_detector import GPUDetector
                        from backend.vfio_manager import VFIOManager
                        
                        detector = GPUDetector()
                        passthrough_gpus = detector.get_passthrough_gpus()
                        
                        if passthrough_gpus:
                            gpu = passthrough_gpus[0]
                            vfio_manager = VFIOManager()
                            
                            # Check if already bound
                            import subprocess
                            result = subprocess.run(
                                ['lspci', '-k', '-s', gpu.pci_address.split(':', 1)[1]],
                                capture_output=True,
                                text=True
                            )
                            
                            if 'vfio-pci' not in result.stdout:
                                logger.info("GPU not bound to VFIO, binding now...")
                                if not vfio_manager.bind_gpu_to_vfio(gpu):
                                    self.finished.emit(False, "Failed to bind GPU to VFIO. Please click 'Activate GPU' first.")
                                    return
                                logger.info("GPU successfully bound to VFIO")
                            else:
                                logger.info("GPU already bound to VFIO")
                    
                    logger.info(f"Starting VM '{self.vm_name}'...")
                    self.domain.create()
                    logger.info(f"VM '{self.vm_name}' started successfully")
                    self.finished.emit(True, "")
                except Exception as e:
                    logger.exception(f"Failed to start VM: {e}")
                    self.finished.emit(False, str(e))
        
        def on_start_finished(success, error):
            self.start_btn.setEnabled(True)
            self.start_btn.setText("▶ Start")
            
            if success:
                # Launch viewer after short delay
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: self._launch_viewer(vm_name))
                # Refresh list
                self.refresh_vm_list()
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Failed to start VM:\n{error}")
        
        # Create and start worker
        self._start_worker = VMStartWorker(domain, vm_name)
        self._start_worker.finished.connect(on_start_finished)
        self._start_worker.start()

    def _launch_viewer(self, vm_name: str):
        """Launch VM viewer - automatically detects Looking Glass or SPICE"""
        try:
            # Get domain object using the correct method
            domain = self.controller.manager.get_vm_by_name(vm_name)
            if not domain:
                logger.error(f"Failed to get domain for '{vm_name}'")
                return
            
            # Use vm_viewer_manager to launch appropriate viewer
            # It will automatically detect Looking Glass and launch it, or fall back to virt-viewer
            success = self.controller.viewer_manager.launch_viewer(
                vm_name=vm_name,
                domain=domain,
                wait_for_vm=True,
                fullscreen=False
            )
            
            if success:
                logger.info(f"Launched viewer for '{vm_name}'")
            else:
                logger.error(f"Failed to launch viewer for '{vm_name}'")
                
        except Exception as e:
            logger.exception(f"Failed to launch viewer: {e}")


    def _on_stop_vm(self):
        """Handle stop VM button"""
        domain = self._get_selected_vm()
        if domain:
            reply = QMessageBox.question(
                self, "Confirm Stop",
                f"Shutdown VM '{domain.name()}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.controller.stop_vm_and_close_viewer(domain)
                self.refresh_vm_list()
    
    def _on_reboot_vm(self):
        """Handle reboot VM button"""
        domain = self._get_selected_vm()
        if domain and self.controller.reboot_vm(domain):
            self.refresh_vm_list()
    
    def _on_delete_vm(self):
        """Handle delete VM button"""
        domain = self._get_selected_vm()
        if not domain:
            return
        
        reply = QMessageBox.warning(
            self, "Confirm Deletion",
            f"Permanently delete VM '{domain.name()}' and its storage?\n\n"
            "This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.manager.delete_vm(domain, remove_storage=True):
                QMessageBox.information(self, "Success", "VM deleted successfully")
                self.refresh_vm_list()
    
    def _on_selection_changed(self):
        """Handle table selection change"""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            uuid = self.table.item(row, 5).text()
            self.vm_selected.emit(uuid)

    def _on_activate_gpu(self):
        """Handle GPU activation button"""
        domain = self._get_selected_vm()
        if not domain:
            return

        from ui.gpu_activation_dialog import GPUActivationDialog
        from backend.gpu_detector import GPUDetector

        detector = GPUDetector()
        passthrough_gpus = detector.get_passthrough_gpus()

        if not passthrough_gpus:
            QMessageBox.warning(
                self,
                "No GPU Available",
                "No GPUs available for passthrough"
            )
            return

        gpu = passthrough_gpus[0]

        dialog = GPUActivationDialog(domain.name(), gpu, self)
        dialog.exec()
        self.refresh_vm_list()
    
    def _on_setup_looking_glass(self):
        """Handle Looking Glass setup button"""
        domain = self._get_selected_vm()
        if not domain:
            return
        
        from backend.looking_glass_manager import LookingGlassManager
        
        # Confirm setup
        reply = QMessageBox.question(
            self,
            "Setup Looking Glass",
            f"This will configure '{domain.name()}' for Looking Glass:\n\n"
            "• Add IVSHMEM shared memory device\n"
            "• Remove QXL video device\n"
            "• Keep SPICE for input only\n\n"
            "After setup, you need to:\n"
            "1. Start the VM\n"
            "2. Install Looking Glass host app in Windows\n"
            "3. Viewer will launch automatically\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        lg_manager = LookingGlassManager()
        
        # Create shared memory file
        if not lg_manager.create_shmem_file(128):
            QMessageBox.critical(
                self,
                "Error",
                "Failed to create shared memory file.\nCheck logs for details."
            )
            return
        
        # Configure VM
        if lg_manager.setup_vm_for_looking_glass(domain, 128):
            QMessageBox.information(
                self,
                "Success",
                f"Looking Glass configured for '{domain.name()}'!\n\n"
                "Next steps:\n"
                "1. Start the VM\n"
                "2. Download Looking Glass host:\n"
                f"   {lg_manager.get_windows_host_download_url()}\n"
                "3. Install and run it in Windows\n"
                "4. Looking Glass viewer will launch automatically!"
            )
            self.refresh_vm_list()
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to configure Looking Glass.\nCheck logs for details."
            )
    
    def _on_install_looking_glass(self):
        """Handle Install Looking Glass button"""
        from backend.looking_glass_manager import LookingGlassManager
        
        lg_manager = LookingGlassManager()
        
        # Check if already installed
        if lg_manager.looking_glass_installed:
            QMessageBox.information(
                self,
                "Already Installed",
                "Looking Glass client is already installed!\n\n"
                f"Location: {subprocess.run(['which', 'looking-glass-client'], capture_output=True, text=True).stdout.strip()}\n\n"
                "You can now use the 'Setup Looking Glass' button to configure your VM."
            )
            return
        
        # Confirm installation
        reply = QMessageBox.question(
            self,
            "Install Looking Glass",
            "This will install Looking Glass client on your system.\n\n"
            "The installation will:\n"
            "• Install build dependencies\n"
            "• Download source code from GitHub\n"
            "• Build and compile Looking Glass\n"
            "• Install to /usr/local/bin\n"
            "• Setup shared memory file\n\n"
            "This may take 5-10 minutes.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Show progress message
        progress = QMessageBox(self)
        progress.setWindowTitle("Installing Looking Glass")
        progress.setText("Installing Looking Glass client...\n\nA terminal window will open.\nPlease wait for installation to complete.")
        progress.setStandardButtons(QMessageBox.NoButton)
        progress.setIcon(QMessageBox.Information)
        progress.show()
        
        # Process events to show the message
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # Install
        success, message = lg_manager.install_looking_glass_client()
        
        progress.close()
        
        if success:
            QMessageBox.information(
                self,
                "Installation Complete",
                f"Looking Glass client installed successfully!\n\n"
                f"Status: {message}\n\n"
                "Next steps:\n"
                "1. Click 'Setup Looking Glass' to configure your VM\n"
                "2. Start the VM\n"
                "3. Install Looking Glass host in Windows\n"
                "4. Enjoy GPU-accelerated display!"
            )
        else:
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Failed to install Looking Glass client.\n\n"
                f"Error: {message}\n\n"
                "You can try installing manually:\n"
                f"cd {subprocess.run(['pwd'], capture_output=True, text=True, cwd='/home/atharv/virtflow').stdout.strip()}\n"
                "./install_looking_glass.sh"
            )
