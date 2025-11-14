"""
VirtFlow Main Window
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QStatusBar, QMenuBar, QMenu,
    QToolBar, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon

import config
from utils.logger import logger
from ui.vm_list_widget import VMListWidget
from models.vm_model import VMModel


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        
        # Initialize UI
        self._setup_ui()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        # self._apply_theme()  <-- REMOVE THIS LINE
        
        # Connect the vm_selected signal to our new slot
        self.vm_list.vm_selected.connect(self.update_status_bar)
        
        logger.info("MainWindow initialized")
    
    def _setup_ui(self):
        """Setup main UI components"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Welcome header
        header = QLabel(f"Welcome to {config.APP_NAME}")
        # --- REMOVE INLINE STYLE ---
        # header.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFFFFF;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel("Modern GPU Passthrough Virtual Machine Manager")
        # --- REMOVE INLINE STYLE ---
        # subtitle.setStyleSheet("font-size: 14px; color: #AAAAAA;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addStretch()
        
        self.vm_list = VMListWidget()
        # --- NEW: Add ObjectName for styling ---
        self.vm_list.setObjectName("VMList")
        layout.addWidget(self.vm_list)
   
    def _create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_vm_action = QAction("&New VM...", self)
        new_vm_action.setShortcut("Ctrl+N")
        new_vm_action.triggered.connect(self._on_create_vm)
        file_menu.addAction(new_vm_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.vm_list.refresh_vm_list)
        view_menu.addAction(refresh_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About VirtFlow", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create toolbar with quick actions"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Add actions (icons will be added in Phase 7)
        new_action = QAction("New VM", self)
        new_action.triggered.connect(self._on_create_vm)
        toolbar.addAction(new_action)
        
        toolbar.addSeparator()
        
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.vm_list.refresh_vm_list)
        toolbar.addAction(refresh_action)
    
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # --- MODIFIED: Create persistent labels with ObjectNames ---
        self.status_vm_name = QLabel("No VM Selected")
        self.status_vm_name.setObjectName("StatusVMName")
        
        self.status_vm_state = QLabel("State: N/A")
        self.status_vm_state.setObjectName("StatusVMState")
        
        self.status_disk_io = QLabel("Disk: 0 B/s")
        self.status_disk_io.setObjectName("StatusDiskIO")
        
        self.status_net_io = QLabel("Net: 0 B/s")
        self.status_net_io.setObjectName("StatusNetIO")
        
        # Add widgets permanently
        self.status_bar.addPermanentWidget(self.status_vm_name)
        self.status_bar.addPermanentWidget(self.status_vm_state)
        self.status_bar.addPermanentWidget(self.status_disk_io)
        self.status_bar.addPermanentWidget(self.status_net_io)
        # --- END MODIFIED SECTION ---
    
    # --- NEW: Helper to format bytes ---
    def _format_bytes_per_sec(self, bytes_val):
        if bytes_val < 1024:
            return f"{bytes_val:.0f} B/s"
        elif bytes_val < 1024**2:
            return f"{bytes_val/1024:.1f} KB/s"
        elif bytes_val < 1024**3:
            return f"{bytes_val/1024**2:.1f} MB/s"
        else:
            return f"{bytes_val/1024**3:.1f} GB/s"

    # --- MODIFIED: Public method to update status bar text ---
    def update_status_bar(self, vm: VMModel, stats: dict):
        if vm:
            self.status_vm_name.setText(f"VM: {vm.name}")
            self.status_vm_state.setText(f"State: {vm.state_name}")
            
            disk_r = self._format_bytes_per_sec(stats.get('disk_read', 0))
            disk_w = self._format_bytes_per_sec(stats.get('disk_write', 0))
            net_rx = self._format_bytes_per_sec(stats.get('net_rx', 0))
            net_tx = self._format_bytes_per_sec(stats.get('net_tx', 0))

            self.status_disk_io.setText(f"Disk: R: {disk_r} W: {disk_w}")
            self.status_net_io.setText(f"Net: RX: {net_rx} TX: {net_tx}")
        else:
            # No VM selected
            self.status_vm_name.setText("No VM Selected")
            self.status_vm_state.setText("State: N/A")
            self.status_disk_io.setText("Disk: 0 B/s")
            self.status_net_io.setText("Net: 0 B/s")
    
    # --- DELETE THE ENTIRE _apply_theme METHOD ---
    # def _apply_theme(self):
    #     ...
    
    # Slot methods
    def _on_create_vm(self):
        """Handle Create VM button click"""
        from ui.create_vm_wizard import CreateVMWizard
    
        wizard = CreateVMWizard(self)
        wizard.vm_created.connect(self.vm_list.refresh_vm_list)
        wizard.exec()
    
    def _on_manage_vms(self):
        """Handle Manage VMs button click"""
        logger.info("Manage VMs clicked")
        QMessageBox.information(
            self,
            "Coming Soon",
            "VM Management will be implemented in Phase 2"
        )
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            f"About {config.APP_NAME}",
            f"<h2>{config.APP_NAME}</h2>"
            f"<p>Version {config.APP_VERSION}</p>"
            f"<p>{config.APP_DESCRIPTION}</p>"
            f"<p>Built with PySide6 and libvirt</p>"
            f"<p>© 2025 {config.APP_AUTHOR}</p>"
        )