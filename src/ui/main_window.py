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
        self._apply_theme()
        
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
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFFFFF;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel("Modern GPU Passthrough Virtual Machine Manager")
        subtitle.setStyleSheet("font-size: 14px; color: #AAAAAA;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addStretch()
        
        self.vm_list = VMListWidget()
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
        toolbar.addAction(refresh_action)
    
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _apply_theme(self):
        """Apply application theme"""
        # This will be enhanced in Phase 7 with proper QSS
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1E1E1E;
            }
            QPushButton {
                background-color: #0D7377;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14FFEC;
                color: #1E1E1E;
            }
            QPushButton:pressed {
                background-color: #0A5F62;
            }
        """)
    
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
