"""
Integrated VM Viewer - Embedded SPICE/VNC viewer in the app
No external virt-viewer needed!
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QFrame
)
from PySide6.QtCore import QProcess, Qt, QTimer
from utils.logger import logger
import subprocess
import time


class IntegratedVMViewer(QWidget):
    """Embedded VM viewer using remote-viewer"""
    
    def __init__(self, vm_name: str, parent=None):
        super().__init__(parent)
        self.vm_name = vm_name
        self.viewer_process = None
        self.viewer_window_id = None
        
        self.setWindowTitle(f"VirtFlow - {vm_name}")
        self.resize(1280, 720)
        
        self._setup_ui()
        self._connect_to_vm()
    
    def _setup_ui(self):
        """Setup UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.StyledPanel)
        toolbar.setMaximumHeight(40)
        toolbar_layout = QHBoxLayout(toolbar)
        
        # VM name label
        self.vm_label = QLabel(f"🖥️ {self.vm_name}")
        self.vm_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #0D7377;")
        toolbar_layout.addWidget(self.vm_label)
        
        toolbar_layout.addStretch()
        
        # Status label
        self.status_label = QLabel("Connecting...")
        self.status_label.setStyleSheet("color: #666;")
        toolbar_layout.addWidget(self.status_label)
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton("⛶ Fullscreen")
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        toolbar_layout.addWidget(self.fullscreen_btn)
        
        # Close button
        close_btn = QPushButton("✕ Close")
        close_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(close_btn)
        
        layout.addWidget(toolbar)
        
        # Viewer container
        self.viewer_container = QFrame()
        self.viewer_container.setFrameStyle(QFrame.StyledPanel)
        self.viewer_container.setStyleSheet("background-color: #000;")
        layout.addWidget(self.viewer_container)
        
        # Info label (shown when viewer not embedded)
        self.info_label = QLabel(
            "🎮 VM Display\n\n"
            "The VM viewer window should open separately.\n"
            "You can view your VM there.\n\n"
            "Close this window when done."
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #999; font-size: 14px;")
        
        container_layout = QVBoxLayout(self.viewer_container)
        container_layout.addWidget(self.info_label)
        
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QFrame {
                background-color: #2B2B2B;
                border: 1px solid #3E3E3E;
            }
            QPushButton {
                background-color: #0D7377;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14FFEC;
                color: #1E1E1E;
            }
        """)
    
    def _connect_to_vm(self):
        """Connect to VM using Looking Glass or fallback to remote-viewer"""
        try:
            # Check if VM has Looking Glass configured
            has_looking_glass = self._check_looking_glass()
            
            if has_looking_glass:
                logger.info("VM has Looking Glass, launching Looking Glass client...")
                self._launch_looking_glass()
            else:
                logger.info("VM doesn't have Looking Glass, using SPICE viewer...")
                self._launch_spice_viewer()
                
        except Exception as e:
            logger.exception(f"Failed to connect to VM: {e}")
            self.status_label.setText("❌ Connection error")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to connect to VM:\n{str(e)}"
            )
    
    def _check_looking_glass(self) -> bool:
        """Check if VM has Looking Glass IVSHMEM device"""
        try:
            result = subprocess.run(
                ['virsh', 'dumpxml', self.vm_name],
                capture_output=True,
                text=True
            )
            return '<shmem name=\'looking-glass\'' in result.stdout
        except:
            return False
    
    def _launch_looking_glass(self):
        """Launch Looking Glass client"""
        try:
            # Check if Looking Glass client is installed
            result = subprocess.run(['which', 'looking-glass-client'], capture_output=True)
            
            if result.returncode != 0:
                self.status_label.setText("❌ Looking Glass not installed")
                QMessageBox.warning(
                    self,
                    "Looking Glass Not Found",
                    "Looking Glass client is not installed.\n\n"
                    "Click '📥 Install Looking Glass' button first.\n\n"
                    "Falling back to SPICE viewer..."
                )
                self._launch_spice_viewer()
                return
            
            # Check if shared memory file exists
            import os
            if not os.path.exists('/dev/shm/looking-glass'):
                self.status_label.setText("❌ Shared memory not found")
                QMessageBox.warning(
                    self,
                    "Shared Memory Missing",
                    "Looking Glass shared memory file not found.\n\n"
                    "Click 'Setup Looking Glass' button first.\n\n"
                    "Falling back to SPICE viewer..."
                )
                self._launch_spice_viewer()
                return
            
            logger.info("Launching Looking Glass client...")
            
            # Get SPICE connection info for keyboard/mouse
            spice_result = subprocess.run(
                ['virsh', 'domdisplay', self.vm_name],
                capture_output=True,
                text=True
            )
            
            spice_uri = spice_result.stdout.strip()
            logger.info(f"SPICE URI: {spice_uri}")
            
            # Extract host and port from spice://127.0.0.1:5900
            # Looking Glass uses: spice:host=X,port=Y format
            spice_args = []
            if spice_uri.startswith('spice://'):
                spice_host_port = spice_uri.replace('spice://', '')
                if ':' in spice_host_port:
                    host, port = spice_host_port.split(':')
                    # Correct format for Looking Glass
                    spice_args = ['spice:host=' + host, 'spice:port=' + port]
                    logger.info(f"Using SPICE: host={host}, port={port}")
            
            # Launch Looking Glass client using Popen (detached process)
            # With window borders and controls for minimize/maximize/close
            lg_args = [
                'looking-glass-client',
                '-f', '/dev/shm/looking-glass',
                '-p', '0',
                '-o', 'win:borderless=no',
                '-o', 'win:minimize=yes',
                '-o', 'win:maximize=yes'
            ]
            
            # Add SPICE connection if available
            if spice_args:
                lg_args.extend(spice_args)
            
            logger.info(f"Launching: {' '.join(lg_args)}")
            self.viewer_process = subprocess.Popen(lg_args)
            
            # Give it a moment to start
            import time
            time.sleep(1)
            
            # Check if process is still running
            if self.viewer_process.poll() is None:
                self.status_label.setText("✓ Looking Glass Running")
                self.info_label.setText(
                    "✓ Looking Glass Viewer Launched\n\n"
                    f"Viewing: {self.vm_name}\n\n"
                    "GPU-accelerated display with near-zero latency!\n\n"
                    "🖱️ MOUSE CONTROL (IMPORTANT!):\n"
                    "• Press ScrollLock to CAPTURE mouse\n"
                    "• Press ScrollLock again to RELEASE mouse\n"
                    "• DO NOT click window - use ScrollLock only!\n\n"
                    "⌨️ KEYBOARD:\n"
                    "• Ctrl+Alt+F: Toggle fullscreen\n"
                    "• Ctrl+Alt+Q: Quit viewer\n"
                    "• If stuck: Press ScrollLock to release!"
                )
                logger.info(f"Looking Glass launched successfully for {self.vm_name}")
            else:
                # Process exited immediately - something wrong
                self.status_label.setText("❌ Looking Glass crashed")
                logger.error("Looking Glass process exited immediately")
                
                # Try to get error
                QMessageBox.warning(
                    self,
                    "Looking Glass Failed",
                    "Looking Glass client crashed on startup.\n\n"
                    "Possible issues:\n"
                    "• Looking Glass host not running in Windows\n"
                    "• Shared memory file permissions\n"
                    "• VM not configured correctly\n\n"
                    "Falling back to SPICE viewer..."
                )
                self._launch_spice_viewer()
                
        except Exception as e:
            logger.exception(f"Failed to launch Looking Glass: {e}")
            self.status_label.setText("❌ Error launching Looking Glass")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to launch Looking Glass:\n{str(e)}\n\nFalling back to SPICE viewer..."
            )
            self._launch_spice_viewer()
    
    def _launch_spice_viewer(self):
        """Launch SPICE viewer (fallback)"""
        try:
            # Get SPICE connection info
            result = subprocess.run(
                ['virsh', 'domdisplay', self.vm_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                self.status_label.setText("❌ Failed to get display info")
                logger.error(f"Failed to get display info: {result.stderr}")
                return
            
            display_uri = result.stdout.strip()
            if not display_uri:
                self.status_label.setText("❌ No display available")
                logger.error("No display URI available")
                return
            
            logger.info(f"Connecting to: {display_uri}")
            
            # Launch remote-viewer
            self.viewer_process = QProcess(self)
            self.viewer_process.finished.connect(self._viewer_closed)
            
            # Try remote-viewer first, fallback to virt-viewer
            viewer_cmd = self._find_viewer()
            
            if viewer_cmd == 'remote-viewer':
                self.viewer_process.start('remote-viewer', [
                    '--title', f'{self.vm_name} - VirtFlow',
                    display_uri
                ])
            else:
                self.viewer_process.start('virt-viewer', [
                    '--connect', 'qemu:///system',
                    '--wait',
                    self.vm_name
                ])
            
            if self.viewer_process.waitForStarted(3000):
                self.status_label.setText("✓ SPICE Connected")
                self.info_label.setText(
                    "✓ SPICE Viewer Connected\n\n"
                    f"Viewing: {self.vm_name}\n\n"
                    "The viewer window is open.\n"
                    "You can minimize this control window."
                )
                logger.info(f"SPICE viewer launched for {self.vm_name}")
            else:
                self.status_label.setText("❌ Viewer failed to start")
                logger.error("Viewer process failed to start")
                
        except Exception as e:
            logger.exception(f"Failed to launch SPICE viewer: {e}")
            self.status_label.setText("❌ Connection error")
    
    def _find_viewer(self):
        """Find available SPICE viewer"""
        for viewer in ['remote-viewer', 'virt-viewer', 'spicy']:
            result = subprocess.run(['which', viewer], capture_output=True)
            if result.returncode == 0:
                return viewer
        return 'virt-viewer'  # Default fallback
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("⛶ Fullscreen")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("⛶ Exit Fullscreen")
    
    def _viewer_closed(self, exit_code, exit_status):
        """Handle viewer process closed"""
        logger.info(f"Viewer closed with code: {exit_code}")
        self.status_label.setText("✕ Viewer closed")
        self.info_label.setText(
            "✕ Viewer Closed\n\n"
            "The VM viewer was closed.\n"
            "You can close this window now."
        )
    
    def closeEvent(self, event):
        """Handle window close"""
        # Check if viewer process is running (handle both QProcess and Popen)
        is_running = False
        if self.viewer_process:
            if hasattr(self.viewer_process, 'state'):
                # QProcess
                is_running = self.viewer_process.state() == QProcess.Running
            elif hasattr(self.viewer_process, 'poll'):
                # subprocess.Popen
                is_running = self.viewer_process.poll() is None
        
        if is_running:
            reply = QMessageBox.question(
                self,
                "Close Viewer?",
                "This will close the VM viewer.\nThe VM will continue running.\n\nClose viewer?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Kill process (handle both QProcess and Popen)
                if hasattr(self.viewer_process, 'kill'):
                    self.viewer_process.kill()
                    if hasattr(self.viewer_process, 'waitForFinished'):
                        # QProcess
                        self.viewer_process.waitForFinished(1000)
                    elif hasattr(self.viewer_process, 'wait'):
                        # subprocess.Popen
                        try:
                            self.viewer_process.wait(timeout=1)
                        except:
                            pass
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
