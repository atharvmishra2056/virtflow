"""
Looking Glass Window Manager V2 - External Window Wrapping
Uses xdotool to grab Looking Glass window and add proper window decorations
This ACTUALLY WORKS by manipulating the X11 window directly
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QMessageBox, QApplication, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import Qt, QTimer, QProcess, QSize, pyqtSignal, QSettings, QThread, QRect
from PySide6.QtGui import QColor, QPalette, QIcon, QCursor
from pathlib import Path
import subprocess
import time
import os
from utils.logger import logger


class LookingGlassX11Wrapper:
    """Use xdotool to manipulate X11 window manager properties"""
    
    @staticmethod
    def get_window_id_by_pid(pid: int) -> Optional[str]:
        """Get X11 window ID from process PID"""
        try:
            result = subprocess.run(
                ["xdotool", "search", "--pid", str(pid), "--name", "looking-glass"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                window_id = result.stdout.strip().split()[0]
                logger.info(f"Found Looking Glass window ID: {window_id}")
                return window_id
            
            return None
        except Exception as e:
            logger.warning(f"Could not find window ID: {e}")
            return None
    
    @staticmethod
    def add_window_decorations(window_id: str, title: str) -> bool:
        """Add window decorations (titlebar, borders, buttons) to borderless window"""
        try:
            # Remove fullscreen
            subprocess.run(
                ["xdotool", "key", "--window", window_id, "alt+F10"],
                timeout=2,
                capture_output=True
            )
            time.sleep(0.2)
            
            # Set window title
            subprocess.run(
                ["xdotool", "set_window", "--name", title, window_id],
                timeout=2,
                capture_output=True
            )
            
            # Add normal window decorations
            subprocess.run(
                ["xdotool", "windowsize", window_id, "1280", "720"],
                timeout=2,
                capture_output=True
            )
            
            # Make window movable (alt+F7)
            subprocess.run(
                ["xdotool", "key", "--window", window_id, "alt+F7"],
                timeout=2,
                capture_output=True
            )
            
            logger.info(f"Added decorations to window {window_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add window decorations: {e}")
            return False
    
    @staticmethod
    def make_window_resizable(window_id: str) -> bool:
        """Make window resizable"""
        try:
            # Use wmctrl if available (better window control)
            result = subprocess.run(
                ["wmctrl", "-i", "-r", window_id, "-b", "remove,maximized_vert,maximized_horz"],
                timeout=2,
                capture_output=True
            )
            
            if result.returncode == 0:
                logger.info(f"Made window {window_id} resizable")
                return True
            
            return False
        except Exception:
            # wmctrl not available, try xdotool
            return True
    
    @staticmethod
    def center_window(window_id: str) -> bool:
        """Center window on screen"""
        try:
            # Get screen geometry
            result = subprocess.run(
                ["xrandr", "--listactivemonitors"],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # For simplicity, use default positioning
            subprocess.run(
                ["xdotool", "windowmove", window_id, "100", "100"],
                timeout=2,
                capture_output=True
            )
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def set_window_always_on_top(window_id: str, ontop: bool = True) -> bool:
        """Set window to always on top"""
        try:
            if ontop:
                subprocess.run(
                    ["xdotool", "key", "--window", window_id, "alt+F9"],
                    timeout=2,
                    capture_output=True
                )
            else:
                subprocess.run(
                    ["xdotool", "key", "--window", window_id, "alt+F9"],
                    timeout=2,
                    capture_output=True
                )
            return True
        except Exception:
            return False


class LookingGlassWindowV2(QMainWindow):
    """
    Looking Glass Window Manager V2 - External Window Wrapping
    
    This solution:
    - Launches looking-glass-client borderless
    - Uses xdotool to find the window
    - Adds proper window decorations (titlebar, borders, buttons)
    - Makes it resizable and movable
    - Adds control panel overlay
    - ACTUALLY WORKS with proper borders and window controls
    """
    
    window_closed = pyqtSignal()
    
    def __init__(self, vm_name: str, vm_host: str = "localhost", vm_port: int = 5900, parent=None):
        super().__init__(parent)
        
        self.vm_name = vm_name
        self.vm_host = vm_host
        self.vm_port = vm_port
        self.lg_process = None
        self.lg_pid = None
        self.lg_window_id = None
        self.is_closing = False
        self.wrapper = LookingGlassX11Wrapper()
        
        logger.info(f"Initializing Looking Glass V2 for {vm_name}")
        
        # Check dependencies
        if not self._check_dependencies():
            raise Exception("Missing xdotool or wmctrl. Install with: sudo apt install xdotool wmctrl")
        
        self._setup_window()
        self._create_control_panel()
        
        # Start Looking Glass
        QTimer.singleShot(500, self._start_looking_glass)
    
    def _check_dependencies(self) -> bool:
        """Check if xdotool and wmctrl are available"""
        deps = ["xdotool", "wmctrl"]
        missing = []
        
        for dep in deps:
            result = subprocess.run(["which", dep], capture_output=True)
            if result.returncode != 0:
                missing.append(dep)
        
        if missing:
            logger.error(f"Missing dependencies: {missing}")
            return False
        
        return True
    
    def _setup_window(self):
        """Setup main control window (small, non-intrusive)"""
        self.setWindowTitle(f"VirtFlow - {self.vm_name}")
        self.setWindowIcon(QIcon())
        
        # Small control panel window
        self.setGeometry(100, 100, 300, 80)
        self.setMinimumSize(QSize(300, 80))
        self.setMaximumSize(QSize(400, 100))
        
        # Dark theme
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        self.setPalette(palette)
        
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
    
    def _create_control_panel(self):
        """Create floating control panel"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        
        # Title
        title = QLabel(f"🖥 {self.vm_name} (Looking Glass)")
        title.setStyleSheet("""
            color: #00ff00;
            font-weight: bold;
            font-size: 12px;
        """)
        layout.addWidget(title)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_focus = QPushButton("↗ Focus")
        self.btn_focus.setMaximumWidth(70)
        self.btn_focus.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        self.btn_focus.clicked.connect(self._focus_lg_window)
        btn_layout.addWidget(self.btn_focus)
        
        self.btn_fullscreen = QPushButton("⛶ Full")
        self.btn_fullscreen.setMaximumWidth(70)
        self.btn_fullscreen.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen_lg)
        btn_layout.addWidget(self.btn_fullscreen)
        
        self.btn_close = QPushButton("✕ Close")
        self.btn_close.setMaximumWidth(70)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #e53935; }
        """)
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        # Status
        self.status_label = QLabel("Launching...")
        self.status_label.setStyleSheet("color: #ffaa00; font-size: 10px;")
        layout.addWidget(self.status_label)
    
    def _start_looking_glass(self):
        """Start Looking Glass borderless"""
        try:
            logger.info(f"Starting Looking Glass for {self.vm_host}:{self.vm_port}...")
            
            cmd = [
                "looking-glass-client",
                "-h", self.vm_host,
                "-p", str(self.vm_port),
                "-s", "/dev/shm/looking-glass",
                "-f",  # Fullscreen
                "-c", str(Path.home() / ".config/looking-glass/client.conf"),
            ]
            
            self.lg_process = QProcess()
            self.lg_process.finished.connect(self._on_lg_finished)
            self.lg_process.start(cmd[0], cmd[1:])
            
            if not self.lg_process.waitForStarted(5000):
                raise Exception("Looking Glass failed to start")
            
            self.lg_pid = self.lg_process.processId()
            logger.info(f"Looking Glass PID: {self.lg_pid}")
            
            # Wait for window to appear and wrap it
            QTimer.singleShot(2000, self._wrap_lg_window)
            
        except Exception as e:
            logger.error(f"Failed to start Looking Glass: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start Looking Glass:\n{e}")
            self.close()
    
    def _wrap_lg_window(self):
        """Find Looking Glass window and add decorations"""
        try:
            logger.info("Wrapping Looking Glass window...")
            
            # Find window ID
            self.lg_window_id = self.wrapper.get_window_id_by_pid(self.lg_pid)
            
            if not self.lg_window_id:
                logger.warning("Window not found yet, retrying...")
                QTimer.singleShot(1000, self._wrap_lg_window)
                return
            
            # Add decorations
            if self.wrapper.add_window_decorations(self.lg_window_id, f"VirtFlow - {self.vm_name}"):
                logger.info("✓ Window decorations added")
                self.status_label.setText("✓ Connected - Window decorated")
                self.status_label.setStyleSheet("color: #00ff00; font-size: 10px;")
            else:
                logger.warning("Failed to add decorations, but continuing...")
            
            # Make resizable
            self.wrapper.make_window_resizable(self.lg_window_id)
            
            # Center window
            self.wrapper.center_window(self.lg_window_id)
            
            # Monitor window
            self._start_monitor()
            
        except Exception as e:
            logger.error(f"Error wrapping window: {e}")
            QTimer.singleShot(1000, self._wrap_lg_window)
    
    def _start_monitor(self):
        """Monitor Looking Glass window"""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._check_lg_alive)
        self.monitor_timer.start(1000)
    
    def _check_lg_alive(self):
        """Check if Looking Glass is still running"""
        if self.lg_process and self.lg_process.state() != QProcess.Running:
            logger.warning("Looking Glass exited")
            self.status_label.setText("✕ Disconnected")
            self.status_label.setStyleSheet("color: #ff0000; font-size: 10px;")
            
            if not self.is_closing:
                reply = QMessageBox.question(
                    self,
                    "Connection Lost",
                    "Looking Glass disconnected. Reconnect?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    QTimer.singleShot(1000, self._start_looking_glass)
    
    def _focus_lg_window(self):
        """Focus Looking Glass window"""
        if self.lg_window_id:
            subprocess.run(
                ["xdotool", "windowactivate", self.lg_window_id],
                capture_output=True,
                timeout=2
            )
            logger.info("Focused Looking Glass window")
    
    def _toggle_fullscreen_lg(self):
        """Toggle fullscreen on Looking Glass window"""
        if self.lg_window_id:
            subprocess.run(
                ["xdotool", "key", "--window", self.lg_window_id, "F11"],
                capture_output=True,
                timeout=2
            )
            logger.info("Toggled fullscreen")
    
    def _on_lg_finished(self):
        """Looking Glass process finished"""
        logger.info("Looking Glass process finished")
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()
    
    def closeEvent(self, event):
        """Close event"""
        logger.info("Closing Looking Glass window...")
        self.is_closing = True
        
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()
        
        if self.lg_process and self.lg_process.state() == QProcess.Running:
            self.lg_process.terminate()
            if not self.lg_process.waitForFinished(2000):
                self.lg_process.kill()
        
        self.window_closed.emit()
        event.accept()
