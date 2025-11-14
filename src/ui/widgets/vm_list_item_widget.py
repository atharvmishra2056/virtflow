"""
VMListItemWidget (Nebula UI)

Custom widget for each item in the Sidebar's QListWidget.
Replicates the look of the items in GG.html.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QPixmap, QPainter, QBrush, QRadialGradient, QColor
from models.vm_model import VMModel
import config
import math

class AnimatedStatusDot(QWidget):
    """Animated status dot that pulses for running VMs"""
    
    def __init__(self, status, parent=None):
        super().__init__(parent)
        self.status = status
        self.setFixedSize(8, 8)
        
        # Animation properties
        self.glow_intensity = 0.0
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.update_pulse)
        
        if status == "running":
            self.pulse_timer.start(50)  # 20 FPS for smooth animation
    
    def update_pulse(self):
        """Update pulse animation"""
        import time
        self.glow_intensity = (math.sin(time.time() * 3) + 1) / 2  # 0 to 1
        self.update()
    
    def paintEvent(self, event):
        """Paint the animated status dot"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        
        if self.status == "running":
            # Green with pulsing glow
            base_color = QColor(34, 197, 94)  # green-500
            
            # Create radial gradient for glow effect
            gradient = QRadialGradient(center_x, center_y, 4)
            
            # Animate the glow
            glow_alpha = int(100 + 155 * self.glow_intensity)
            gradient.setColorAt(0, QColor(34, 197, 94, 255))
            gradient.setColorAt(0.7, QColor(34, 197, 94, glow_alpha))
            gradient.setColorAt(1, QColor(34, 197, 94, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 8, 8)
            
        elif self.status == "stopped":
            # Red dot
            painter.setBrush(QBrush(QColor(239, 68, 68)))  # red-500
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(1, 1, 6, 6)
            
        elif self.status == "paused":
            # Yellow dot
            painter.setBrush(QBrush(QColor(234, 179, 8)))  # yellow-500
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(1, 1, 6, 6)
        
        painter.end()

class VMListItemWidget(QWidget):
    def __init__(self, vm: VMModel, parent=None):
        super().__init__(parent)
        self.vm = vm

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(12, 10, 12, 10) # p-3
        self.main_layout.setSpacing(12) # gap-3

        # 1. OS Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(QSize(40, 40)) # w-10 h-10
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # Set OS icon based on VM name/type (using SVG icons)
        if "win" in vm.name.lower() or "windows" in vm.name.lower():
            icon_path = config.ICONS_DIR / "windows-logo.svg"
            bg_gradient = "stop:0 #2563eb, stop:1 #06b6d4"  # blue to cyan
        elif "ubuntu" in vm.name.lower() or "linux" in vm.name.lower():
            icon_path = config.ICONS_DIR / "linux-logo.svg"
            bg_gradient = "stop:0 #ea580c, stop:1 #ef4444"  # orange to red
        elif "mac" in vm.name.lower():
            icon_path = config.ICONS_DIR / "apple-logo.svg"
            bg_gradient = "stop:0 #e5e7eb, stop:1 #9ca3af"  # light gray
        else:
            icon_path = config.ICONS_DIR / "cpu.svg"  # Generic computer icon
            bg_gradient = "stop:0 #6366f1, stop:1 #8b5cf6"  # indigo to purple
        
        # Load and set the SVG icon
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.setText("💻")  # Fallback to emoji
            
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, {bg_gradient});
                border-radius: 8px;
            }}
        """)

        # 2. Text Content (Name + Status)
        self.text_layout = QVBoxLayout()
        self.text_layout.setSpacing(0)
        self.text_layout.setContentsMargins(0, 0, 0, 0)
        
        self.vm_name_label = QLabel(vm.name)
        self.vm_name_label.setStyleSheet("font-weight: 500; color: #FFFFFF;")

        self.status_text_label = QLabel(f"{vm.state_name} • {vm.max_memory_mb // 1024}GB RAM")
        self.status_text_label.setStyleSheet("font-size: 8pt; color: #94a3b8;") # slate-400

        self.text_layout.addWidget(self.vm_name_label)
        self.text_layout.addWidget(self.status_text_label)

        # 3. Animated Status Dot
        self.status_dot = AnimatedStatusDot(vm.state_name.lower())
        
        # Add to main layout
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addLayout(self.text_layout, 1) # 1 = stretch
        self.main_layout.addWidget(self.status_dot, 0, Qt.AlignTop | Qt.AlignRight)

        # Set a fixed height for the whole widget
        self.setFixedHeight(self.sizeHint().height())
    
    def update_data(self, vm: VMModel):
        """Refreshes the widget with new VM data"""
        self.vm = vm
        self.vm_name_label.setText(vm.name)
        self.status_text_label.setText(f"{vm.state_name} • {vm.max_memory_mb // 1024}GB RAM")
        
        # Update animated status dot
        old_status = self.status_dot.status
        new_status = vm.state_name.lower()
        
        if old_status != new_status:
            # Replace with new animated dot if status changed
            self.main_layout.removeWidget(self.status_dot)
            self.status_dot.deleteLater()
            self.status_dot = AnimatedStatusDot(new_status)
            self.main_layout.addWidget(self.status_dot, 0, Qt.AlignTop | Qt.AlignRight)