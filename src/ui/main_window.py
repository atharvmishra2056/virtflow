"""
VirtFlow Main Window (Nebula UI)
This is the frameless main window container.
Now with resizers and signal/slot connections.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSizeGrip, QStatusBar, QVBoxLayout, QFrame,
    QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

import config
from utils.logger import logger
from models.vm_model import VMModel # Import for type hint

# --- NEW UI IMPORTS ---
from ui.title_bar import TitleBarWidget
from ui.sidebar_widget import SidebarWidget
from ui.main_stage_widget import MainStageWidget
from ui.animated_background import AnimatedBackground
# ---------------------------

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle(config.APP_NAME)
        
        # --- MAKE FRAMELESS ---
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Allows for custom rounded corners
        
        # --- SIMPLIFIED STRUCTURE ---
        # The glass_panel IS the central widget.
        self.glass_panel = QFrame()
        self.glass_panel.setObjectName("GlassPanel")
        
        # This inline style is CRITICAL for the frameless window to work.
        # It sets the opaque background color and rounds the corners.
        self.glass_panel.setStyleSheet(f"""
            QFrame#GlassPanel {{
                background-color: {config.COLOR_BACKGROUND}; /* Use config color */
                border-radius: 20px;
                /* Borders are applied from nebula.qss */
            }}
        """)
        
        # Add animated background behind glass panel
        self.animated_bg = AnimatedBackground(self)
        self.animated_bg.setGeometry(0, 0, 1200, 800)
        self.animated_bg.lower()  # Send to back
        
        # Set the glass panel as the central widget
        self.setCentralWidget(self.glass_panel)
        
        # Main layout for the glass panel
        self.main_layout = QVBoxLayout(self.glass_panel)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # --- END SIMPLIFIED STRUCTURE ---
        
        self.setMinimumSize(1200, 800)
        
        # Store window geometry for dragging
        self.drag_start_position = None
        self.window_start_position = None

        # Initialize UI
        self._setup_ui()
        
        # --- NEW: Add resizers ---
        self._add_resizers()
        
        logger.info("MainWindow initialized")

    def _setup_ui(self):
        """Setup main UI components"""
        
        # 1. Title Bar
        self.title_bar = TitleBarWidget(self)
        
        # 2. Main Content Area (Sidebar + Stage)
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(0)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # 2a. Sidebar
        self.sidebar = SidebarWidget(self)
        
        # 2b. Main Stage
        self.main_stage = MainStageWidget(self)
        
        self.content_layout.addWidget(self.sidebar)
        self.content_layout.addWidget(self.main_stage, 1) # 1 = stretch factor
        
        # 3. Add to main layout
        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addLayout(self.content_layout, 1) # 1 = stretch factor

        # --- Connect Signals ---
        # When a VM is selected in the sidebar, tell the main stage to update
        self.sidebar.vm_selected.connect(self.main_stage.update_vm_info)
        
        # Connect main stage buttons to sidebar logic
        self.main_stage.start_stop_btn.clicked.connect(self.sidebar.on_start_stop_vm)
        self.main_stage.pause_btn.clicked.connect(self.sidebar.on_pause_vm)
        self.main_stage.reboot_btn.clicked.connect(self.sidebar.on_reboot_vm)
        
        # Connect "Create VM" button
        self.sidebar.new_vm_btn.clicked.connect(self._on_create_vm)
        
        # Connect search functionality
        self.title_bar.search_changed.connect(self.sidebar.filter_vms)
        
        # Connect setup menu actions (we will create these in Phase 1)
        # self.title_bar.setup_sudo_action.triggered.connect(...) 

    def _add_resizers(self):
        """Add resize grips to corners for window resizing"""
        # Bottom-right corner grip (most important)
        self.corner_grip = QSizeGrip(self)
        self.corner_grip.setFixedSize(20, 20)
        self.corner_grip.setStyleSheet("""
            QSizeGrip { 
                background: transparent; 
                image: url(); /* Remove default grip image */
            }
        """)
        
        # Position the grip in the bottom-right corner
        self.corner_grip.move(self.width() - 20, self.height() - 20)
        self.corner_grip.raise_()
        
        # Add additional grips for better UX
        self.bottom_grip = QSizeGrip(self)
        self.bottom_grip.setFixedSize(self.width() - 40, 10)
        self.bottom_grip.move(20, self.height() - 10)
        self.bottom_grip.setStyleSheet("QSizeGrip { background: transparent; }")
        
        self.right_grip = QSizeGrip(self)
        self.right_grip.setFixedSize(10, self.height() - 40)
        self.right_grip.move(self.width() - 10, 20)
        self.right_grip.setStyleSheet("QSizeGrip { background: transparent; }")

    def mousePressEvent(self, event):
        """Handle mouse press for window dragging"""
        if event.button() == Qt.LeftButton:
            # Only drag if clicking on the title bar or empty areas
            widget_under_mouse = self.childAt(event.position().toPoint())
            if (widget_under_mouse is None or 
                widget_under_mouse == self.glass_panel or
                (hasattr(widget_under_mouse, 'objectName') and 
                 widget_under_mouse.objectName() in ['TitleBarWidget', 'TitleBarLogo', 'TitleBarSubtitle'])):
                self.drag_start_position = event.globalPosition().toPoint()
                self.window_start_position = self.pos()
                event.accept()
            else:
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging"""
        if (event.buttons() == Qt.LeftButton and 
            hasattr(self, 'drag_start_position') and 
            self.drag_start_position is not None):
            
            # Calculate the distance moved
            delta = event.globalPosition().toPoint() - self.drag_start_position
            
            # Move the window
            new_pos = self.window_start_position + delta
            self.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_start_position = None
            self.window_start_position = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
        
    def resizeEvent(self, event):
        """Reposition resize grips when window is resized"""
        super().resizeEvent(event)
        if hasattr(self, 'corner_grip'):
            self.corner_grip.move(self.width() - 20, self.height() - 20)
        if hasattr(self, 'bottom_grip'):
            self.bottom_grip.setFixedSize(self.width() - 40, 10)
            self.bottom_grip.move(20, self.height() - 10)
        if hasattr(self, 'right_grip'):
            self.right_grip.setFixedSize(10, self.height() - 40)
            self.right_grip.move(self.width() - 10, 20)
        
        # Update animated background size
        if hasattr(self, 'animated_bg'):
            self.animated_bg.setGeometry(0, 0, self.width(), self.height())

    def _on_create_vm(self):
        """Handle Create VM button click"""
        from ui.create_vm_wizard import CreateVMWizard
    
        wizard = CreateVMWizard(self)
        wizard.vm_created.connect(self.sidebar.refresh_vm_list)
        wizard.exec()