"""
VirtFlow Main Window (Nebula UI)
This is the frameless main window container.
Now with resizers and signal/slot connections.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSizeGrip, QStatusBar, QVBoxLayout, QFrame,
    QMessageBox
)
from PySide6.QtCore import Qt, QSize, QProcess, Slot
from PySide6.QtGui import QIcon, QGuiApplication

import config
from utils.logger import logger
from models.vm_model import VMModel # Import for type hint
import os
import subprocess

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
        
        # Connect search signal from title bar to sidebar filtering
        self.title_bar.search_changed.connect(self.sidebar.filter_vms)
        
        # --- NEW: Connect Setup Menu Actions ---
        self.title_bar.setup_sudo_action.triggered.connect(self._on_setup_sudo)
        self.title_bar.setup_hooks_action.triggered.connect(self._on_setup_hooks)
        self.title_bar.setup_lg_action.triggered.connect(self._on_install_looking_glass)
        # --- END NEW ---
        
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

    # --- NEW: Sudo setup dialog ---
    @Slot()
    def _on_setup_sudo(self):
        from backend.vfio_manager import VFIOManager
        sudo_file_path = "/etc/sudoers.d/virtflow-gpu"
        
        if os.path.exists(sudo_file_path):
             QMessageBox.information(self, "Permissions OK",
                f"Sudo permissions file already exists at:\n{sudo_file_path}\n\n"
                "No action needed.")
             return

        sudo_content = VFIOManager.get_sudoers_content()
        cmd = f"sudo EDITOR='tee' visudo -f {sudo_file_path}"

        msg = QMessageBox(self)
        msg.setWindowTitle("Action Required: Sudo Permissions")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(
            "VirtFlow needs passwordless `sudo` access for specific commands "
            "(like `modprobe`) to manage GPU drivers.\n\n"
            "This is the safest method as it validates the file's syntax."
        )
        msg.setInformativeText(f"<b>Command to run:</b><pre>{cmd}</pre>"
                               "Click 'Copy Command', paste it in your terminal, "
                               "and then paste the content (from 'Show Details') when prompted by `tee`.")
        msg.setDetailedText(f"--- Content to paste: ---\n\n{sudo_content}")
        
        copy_cmd_btn = msg.addButton("Copy Command", QMessageBox.ActionRole)
        msg.addButton("Done", QMessageBox.AcceptRole)

        msg.exec()

        if msg.clickedButton() == copy_cmd_btn:
            QGuiApplication.clipboard().setText(cmd)
            QMessageBox.information(self, "Command Copied", "Command copied to clipboard. Please paste it into your terminal.")

    # --- NEW: Libvirt hook setup dialog ---
    @Slot()
    def _on_setup_hooks(self):
        hook_file_path = "/etc/libvirt/hooks/qemu"
        
        if os.path.exists(hook_file_path):
            QMessageBox.information(self, "Hook Already Exists",
                f"The libvirt hook file already exists:\n{hook_file_path}\n\n"
                "VirtFlow will not overwrite it. Please ensure it contains the "
                "logic from the VirtFlow documentation if you set it up manually.")
            return

        # Fetch content from the install script.
        # This is safer than reading the file in case it moves.
        hook_content = """#!/bin/bash
# Libvirt QEMU hook for GPU passthrough management
# This hook is called by libvirt when VM state changes

GUEST_NAME="$1"
OPERATION="$2"
SUB_OPERATION="$3"

LOG_FILE="/var/log/libvirt/qemu-hook.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$GUEST_NAME] $1" >> "$LOG_FILE"
}

# Check if VM has GPU passthrough (look for hostdev in XML)
has_gpu_passthrough() {
    virsh dumpxml "$GUEST_NAME" 2>/dev/null | grep -q '<hostdev.*type=.pci'
}

log "Hook called: operation=$OPERATION sub_operation=$SUB_OPERATION"

if ! has_gpu_passthrough; then
    log "No GPU passthrough detected, skipping"
    exit 0
fi

case "$OPERATION" in
    "prepare")
        case "$SUB_OPERATION" in
            "begin")
                log "VM starting - GPU should already be bound to VFIO"
                ;;
        esac
        ;;
    
    "release")
        case "$SUB_OPERATION" in
            "end")
                log "VM stopped - GPU will be restored to host by vm_controller"
                ;;
        esac
        ;;
esac

exit 0
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Action Required: Install Libvirt Hook")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(
            "To automatically manage GPU states, VirtFlow uses a libvirt hook script.\n\n"
            "Please run these commands in a terminal to create and enable the hook."
        )
        
        cmd1 = f"echo '{hook_content}' | sudo tee {hook_file_path}"
        cmd2 = f"sudo chmod +x {hook_file_path}"
        cmd3 = "sudo systemctl restart libvirtd"

        msg.setInformativeText(
            f"<b>Commands to run (one by one):</b>\n"
            f"<pre>{cmd1}</pre>\n"
            f"<pre>{cmd2}</pre>\n"
            f"<pre>{cmd3}</pre>"
        )
        msg.addButton("Done", QMessageBox.AcceptRole)
        msg.exec()


    # --- NEW: Logic moved from vm_list_widget.py ---
    @Slot()
    def _on_install_looking_glass(self):
        from backend.looking_glass_manager import LookingGlassManager
        
        lg_manager = LookingGlassManager()
        
        if lg_manager.looking_glass_installed:
            QMessageBox.information(
                self,
                "Already Installed",
                "Looking Glass client is already installed!\n\n"
                f"Location: {subprocess.run(['which', 'looking-glass-client'], capture_output=True, text=True).stdout.strip()}\n\n"
                "You can now use the 'Display Preference' menu on a VM."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Install Looking Glass Client",
            "This will attempt to install the Looking Glass client by compiling it from source.\n\n"
            "This requires `sudo` access to install build dependencies (like cmake, libdecor-dev) and the final binary.\n\n"
            "A terminal window will open. You may need to enter your password there.\n"
            "This may take 5-10 minutes.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # --- This now uses the embedded script ---
        try:
            # 1. Get the content of the install script
            script_path = config.BASE_DIR.parent / "install_looking_glass.sh"
            with open(script_path, 'r') as f:
                script_content = f.read()
            
            # 2. Write it to a temp file
            temp_script_path = "/tmp/virtflow_lg_install.sh"
            with open(temp_script_path, 'w') as f:
                f.write(script_content)
            
            os.chmod(temp_script_path, 0o755) # Make it executable

            # 3. Launch it in a terminal
            # This is the most reliable cross-platform way
            QProcess.startDetached('x-terminal-emulator', ['-e', temp_script_path])
            
            QMessageBox.information(
                self,
                "Installation Started",
                "Installation has started in a new terminal window.\n\n"
                "Please follow the prompts and wait for it to complete, then restart VirtFlow."
            )

        except Exception as e:
            logger.error(f"Failed to launch Looking Glass installer: {e}")
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Failed to launch the installer: {e}\n\n"
                "Please run `install_looking_glass.sh` manually."
            )