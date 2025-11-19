"""
MainStageWidget (Nebula UI)
This is the main content area, including the VM toolbar,
preview, and stats panels.
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QWidget, QProgressBar, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor, QBrush

import config
from ui.widgets.icon_utils import create_recolored_icon
from models.vm_model import VMModel
from backend.vm_controller import VMState
from utils.logger import logger
import random
import math
try:
    import psutil
except ImportError:
    psutil = None

class MainStageWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainStage")
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. VM Toolbar
        self.toolbar = self._create_vm_toolbar()
        
        # 2. Main Workspace
        self.workspace_layout = QHBoxLayout()
        self.workspace_layout.setContentsMargins(24, 24, 24, 24) # p-8
        self.workspace_layout.setSpacing(24) # gap-6

        # 2a. Center Panel (Preview + Console)
        self.center_panel = self._create_center_panel()

        # 2b. Right Stats Panel
        self.stats_panel = self._create_stats_panel()

        self.workspace_layout.addWidget(self.center_panel, 1) # 1 = stretch
        self.workspace_layout.addWidget(self.stats_panel)

        self.main_layout.addWidget(self.toolbar)
        self.main_layout.addLayout(self.workspace_layout, 1) # 1 = stretch
        
        # Initialize system monitoring
        self.cpu_history = [0] * 30
        self._init_system_monitoring()
        
        # Set initial empty state
        self.update_vm_info(None, {})

    def _create_vm_toolbar(self) -> QFrame:
        """Creates the top VM toolbar (Start, Stop, etc.)"""
        toolbar = QFrame()
        toolbar.setObjectName("VMToolbar")
        toolbar.setFixedHeight(64) # h-16
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(24, 0, 24, 0) # px-6
        layout.setSpacing(16)

        self.vm_name_label = QLabel("No VM Selected")
        self.vm_name_label.setObjectName("ActiveVMName")
        
        self.vm_status_badge = QLabel("N/A")
        self.vm_status_badge.setObjectName("ActiveVMStatus")
        self.vm_status_badge.setProperty("status", "stopped") # For QSS

        layout.addWidget(self.vm_name_label)
        layout.addWidget(self.vm_status_badge)
        layout.addStretch()

        # --- Glass Buttons (Floating style like GG.html) ---
        self.start_stop_btn = QPushButton(" Stop")
        # --- PHASE 2 (REDUX) TASK 2: Use global QSS ---
        # self.start_stop_btn.setObjectName("GlassButton") # No longer needed, auto-inherits
        self.start_stop_btn.setProperty("class", "GlassButton") # Explicitly set class
        # Load power icon
        power_icon = create_recolored_icon(str(config.ICONS_DIR / "power.svg"), QColor("#e2e8f0"))
        self.start_stop_btn.setIcon(power_icon)
        # --- All inline QSS removed ---
        
        self.pause_btn = QPushButton()
        self.pause_btn.setProperty("class", "GlassButton")
        self.pause_btn.setIcon(create_recolored_icon(str(config.ICONS_DIR / "pause.svg"), QColor("#e2e8f0")))
        self.pause_btn.setFixedSize(40, 40)
        
        self.reboot_btn = QPushButton()
        self.reboot_btn.setProperty("class", "GlassButton") 
        self.reboot_btn.setIcon(create_recolored_icon(str(config.ICONS_DIR / "arrows-clockwise.svg"), QColor("#e2e8f0")))
        self.reboot_btn.setFixedSize(40, 40)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFixedWidth(1)
        separator.setFixedHeight(24)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.2);")

        self.snapshot_btn = QPushButton()
        self.snapshot_btn.setProperty("class", "GlassButton")
        self.snapshot_btn.setIcon(create_recolored_icon(str(config.ICONS_DIR / "camera.svg"), QColor("#e2e8f0")))
        self.snapshot_btn.setFixedSize(40, 40)
        
        self.monitor_btn = QPushButton() # "🖥️"
        self.monitor_btn.setProperty("class", "GlassButton")
        # self.monitor_btn.setIcon(QIcon(str(config.ICONS_DIR / "monitor.svg"))) # Assuming we add this icon
        self.monitor_btn.setIcon(create_recolored_icon(str(config.ICONS_DIR / "monitor.svg"), QColor("#e2e8f0")))
        self.monitor_btn.setFixedSize(40, 40)

        layout.addWidget(self.start_stop_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.reboot_btn)
        layout.addWidget(separator)
        layout.addWidget(self.snapshot_btn)
        layout.addWidget(self.monitor_btn)
        
        return toolbar

    def _create_center_panel(self) -> QWidget:
        """Creates the VM Preview and Console/Log panel"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16) # gap-4

        # 1. VM Preview
        self.vm_preview = QLabel("No VM Selected. Please select a machine from the left panel.")
        self.vm_preview.setObjectName("VMPreview")
        self.vm_preview.setMinimumHeight(300)
        self.vm_preview.setAlignment(Qt.AlignCenter)
        self.vm_preview.setStyleSheet("""
            border: 1px dashed rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: #94a3b8;
            font-size: 14pt;
        """)
        
        # Store the default pixmap
        try:
            win11_path = config.BASE_DIR / "ui" / "assets" / "images" / "Win11.jpg"
            if win11_path.exists():
                self.default_pixmap = QPixmap(str(win11_path))
            else:
                # Create a placeholder if image doesn't exist
                self.default_pixmap = QPixmap(800, 600)
                self.default_pixmap.fill(Qt.black)
                logger.warning(f"Win11.jpg not found at {win11_path}")
        except Exception as e:
            logger.error(f"Failed to load Win11.jpg: {e}")
            self.default_pixmap = QPixmap(800, 600)
            self.default_pixmap.fill(Qt.black)

        # 2. Console/Log Tabs
        self.console_tabs = QTabWidget()
        self.console_tabs.setFixedHeight(200) # h-48

        # Log Tab
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("ConsoleLog")
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)

        # Terminal Tab
        term_widget = QWidget()
        term_layout = QVBoxLayout(term_widget)
        term_layout.setContentsMargins(0, 0, 0, 0)
        self.term_output = QTextEdit()
        self.term_output.setObjectName("ConsoleLog")
        self.term_output.setReadOnly(True)
        self.term_output.setText("Waiting for VM connection...")
        term_layout.addWidget(self.term_output)

        self.console_tabs.addTab(term_widget, "Terminal")
        self.console_tabs.addTab(log_widget, "Logs")
        
        layout.addWidget(self.vm_preview, 1) # 1 = stretch
        layout.addWidget(self.console_tabs)
        
        return container

    def _create_stats_panel(self) -> QFrame:
        """Creates the right-hand stats panel"""
        panel = QFrame()
        panel.setObjectName("StatsPanel")
        panel.setFixedWidth(288) # w-72
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16) # gap-4

        # 1. CPU Widget
        cpu_widget = QFrame()
        cpu_widget.setObjectName("GlassPanel")
        cpu_layout = QVBoxLayout(cpu_widget)
        cpu_layout.setContentsMargins(16, 16, 16, 16) # p-4
        
        cpu_title_layout = QHBoxLayout()
        cpu_title = QLabel("CPU USAGE")
        cpu_title.setObjectName("StatsTitle")
        self.cpu_cores_label = QLabel("N/A")
        self.cpu_cores_label.setObjectName("StatsSubText")
        cpu_title_layout.addWidget(cpu_title)
        cpu_title_layout.addStretch()
        cpu_title_layout.addWidget(self.cpu_cores_label)
        
        self.cpu_percent_label = QLabel("0%")
        self.cpu_percent_label.setObjectName("StatsBigText")
        
        cpu_layout.addLayout(cpu_title_layout)
        cpu_layout.addStretch()
        # CPU Graph
        self.cpu_graph = QWidget()
        self.cpu_graph.setFixedSize(200, 60)
        self.cpu_graph.paintEvent = self._paint_cpu_graph
        cpu_layout.addWidget(self.cpu_graph, 1)
        cpu_layout.addStretch()
        cpu_layout.addWidget(self.cpu_percent_label)

        # 2. Memory Widget
        mem_widget = QFrame()
        mem_widget.setObjectName("GlassPanel")
        mem_layout = QVBoxLayout(mem_widget)
        mem_layout.setContentsMargins(16, 16, 16, 16) # p-4
        
        mem_title_layout = QHBoxLayout()
        mem_title = QLabel("MEMORY")
        mem_title.setObjectName("StatsTitle")
        self.mem_total_label = QLabel("0 GB")
        self.mem_total_label.setObjectName("StatsSubText")
        mem_title_layout.addWidget(mem_title)
        mem_title_layout.addStretch()
        mem_title_layout.addWidget(self.mem_total_label)
        
        self.mem_bar = QProgressBar()
        self.mem_bar.setObjectName("RAMBar")
        self.mem_bar.setFixedHeight(8)
        self.mem_bar.setTextVisible(False)
        
        mem_stats_layout = QHBoxLayout()
        self.mem_used_label = QLabel("Used: 0 GB")
        self.mem_used_label.setObjectName("StatsSubText")
        self.mem_free_label = QLabel("Free: 0 GB")
        self.mem_free_label.setObjectName("StatsSubText")
        mem_stats_layout.addWidget(self.mem_used_label)
        mem_stats_layout.addStretch()
        mem_stats_layout.addWidget(self.mem_free_label)
        
        mem_layout.addLayout(mem_title_layout)
        mem_layout.addSpacing(12)
        mem_layout.addWidget(self.mem_bar)
        mem_layout.addSpacing(4)
        mem_layout.addLayout(mem_stats_layout)

        # 3. Storage Widget
        disk_widget = QFrame()
        disk_widget.setObjectName("GlassPanel")
        disk_layout = QVBoxLayout(disk_widget)
        disk_layout.setContentsMargins(16, 16, 16, 16) # p-4
        
        disk_title_layout = QHBoxLayout()
        disk_title = QLabel("STORAGE (Read/Write)")
        disk_title.setObjectName("StatsTitle")
        disk_title_layout.addWidget(disk_title)
        disk_layout.addLayout(disk_title_layout)
        disk_layout.addSpacing(12)

        self.disk_read_label = QLabel("R: 0 B/s")
        self.disk_read_label.setObjectName("StatsSubText")
        self.disk_write_label = QLabel("W: 0 B/s")
        self.disk_write_label.setObjectName("StatsSubText")
        
        disk_layout.addWidget(self.disk_read_label)
        disk_layout.addWidget(self.disk_write_label)
        disk_layout.addStretch()
        
        layout.addWidget(cpu_widget)
        layout.addWidget(mem_widget)
        layout.addWidget(disk_widget)
        layout.addStretch() # Push everything to the top
        
        # Initialize system monitoring
        self.cpu_history = [0] * 30
        self._init_system_monitoring()
        
        return panel

    def _format_bytes(self, b):
        if b < 1024: return f"{b} B"
        elif b < 1024**2: return f"{b/1024:.1f} KB"
        elif b < 1024**3: return f"{b/1024**2:.1f} MB"
        else: return f"{b/1024**3:.1f} GB"

    def _format_bytes_per_sec(self, b):
        return f"{self._format_bytes(b)}/s"

    # --- THIS IS THE SLOT THAT FIXES YOUR ERROR ---
    def update_vm_info(self, vm: VMModel | None, stats: dict):
        """
        Public slot to update the entire main stage based on
        the selected VM.
        """
        if vm is None:
            # No VM selected
            self.vm_name_label.setText("No VM Selected")
            self.vm_status_badge.setText("N/A")
            self.vm_status_badge.setProperty("status", "stopped")
            
            self.start_stop_btn.setText(" Start")
            self.start_stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.reboot_btn.setEnabled(False)
            self.snapshot_btn.setEnabled(False)
            self.monitor_btn.setEnabled(False)

            self.vm_preview.setText("No VM Selected. Please select a machine from the left panel.")
            self.vm_preview.setPixmap(QPixmap()) # Clear pixmap
            
            self.cpu_percent_label.setText("0%")
            self.cpu_cores_label.setText("N/A")
            self.mem_bar.setValue(0)
            self.mem_total_label.setText("0 GB")
            self.mem_used_label.setText("Used: 0 GB")
            self.mem_free_label.setText("Free: 0 GB")
            self.disk_read_label.setText("R: 0 B/s")
            self.disk_write_label.setText("W: 0 B/s")
        
        else:
            # A VM is selected
            is_running = vm.state == VMState.RUNNING
            is_off = vm.state == VMState.SHUTOFF
            
            self.vm_name_label.setText(vm.name)
            self.vm_status_badge.setText(vm.state_name.upper())
            self.vm_status_badge.setProperty("status", vm.state_name.lower().replace(" ", "_"))

            # Update buttons
            self.start_stop_btn.setEnabled(is_running or is_off)
            self.start_stop_btn.setText(" Stop" if is_running else " Start")
            self.start_stop_btn.setProperty("status", "running" if is_running else "stopped")
            
            self.pause_btn.setEnabled(is_running)
            self.reboot_btn.setEnabled(is_running)
            self.snapshot_btn.setEnabled(True)
            self.monitor_btn.setEnabled(True)

            # Update Preview
            self.vm_preview.setPixmap(self.default_pixmap.scaled(
                self.vm_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            # Update Stats
            self.cpu_cores_label.setText(f"{vm.vcpus} Cores")
            
            mem_total_gb = vm.max_memory_mb / 1024
            mem_curr_gb = vm.current_memory_mb / 1024
            mem_perc = (vm.current_memory_mb / vm.max_memory_mb) * 100 if vm.max_memory_mb > 0 else 0
            
            self.mem_bar.setValue(int(mem_perc))
            self.mem_total_label.setText(f"{mem_total_gb:.0f} GB")
            self.mem_used_label.setText(f"Used: {mem_curr_gb:.1f} GB")
            self.mem_free_label.setText(f"Free: {mem_total_gb - mem_curr_gb:.1f} GB")

            if is_running:
                self.disk_read_label.setText(f"R: {self._format_bytes_per_sec(stats.get('disk_read', 0))}")
                self.disk_write_label.setText(f"W: {self._format_bytes_per_sec(stats.get('disk_write', 0))}")
            else:
                self.disk_read_label.setText("R: 0 B/s")
                self.disk_write_label.setText("W: 0 B/s")
        
        # Re-apply stylesheet to update properties
        self.vm_status_badge.style().unpolish(self.vm_status_badge)
        self.vm_status_badge.style().polish(self.vm_status_badge)
        self.start_stop_btn.style().unpolish(self.start_stop_btn)
        self.start_stop_btn.style().polish(self.start_stop_btn)
    
    def _init_system_monitoring(self):
        """Initialize system monitoring timer"""
        self.system_timer = QTimer()
        self.system_timer.timeout.connect(self._update_system_stats)
        self.system_timer.start(2000)  # Update every 2 seconds
        self._update_system_stats()  # Initial update
    
    def _paint_cpu_graph(self, event):
        """Paint CPU usage graph"""
        painter = QPainter(self.cpu_graph)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.cpu_graph.rect(), QColor(0, 0, 0, 0)) # Fully transparent bg
        
        # Draw grid lines
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        for i in range(0, 101, 25):
            y = self.cpu_graph.height() - (i / 100) * self.cpu_graph.height()
            painter.drawLine(0, y, self.cpu_graph.width(), y)
        
        # Draw CPU line
        if len(self.cpu_history) > 1:
            painter.setPen(QPen(QColor(99, 102, 241), 2))  # Indigo
            
            step_x = self.cpu_graph.width() / (len(self.cpu_history) - 1)
            
            for i in range(len(self.cpu_history) - 1):
                x1 = i * step_x
                y1 = self.cpu_graph.height() - (self.cpu_history[i] / 100) * self.cpu_graph.height()
                x2 = (i + 1) * step_x
                y2 = self.cpu_graph.height() - (self.cpu_history[i + 1] / 100) * self.cpu_graph.height()
                
                painter.drawLine(x1, y1, x2, y2)
        
        painter.end()
    
    def _update_system_stats(self):
        """Update system statistics in the right panel"""
        try:
            if psutil:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=None)
                self.cpu_percent_label.setText(f"{cpu_percent:.1f}%")
                
                # Update CPU history
                self.cpu_history.append(cpu_percent)
                if len(self.cpu_history) > 30:
                    self.cpu_history.pop(0)
                
                # CPU cores
                cpu_count = psutil.cpu_count()
                self.cpu_cores_label.setText(f"{cpu_count} cores")
                
                # Memory
                memory = psutil.virtual_memory()
                used_gb = memory.used / (1024**3)
                total_gb = memory.total / (1024**3)
                self.mem_total_label.setText(f"{total_gb:.1f} GB")
                self.mem_used_label.setText(f"Used: {used_gb:.1f} GB")
                self.mem_free_label.setText(f"Free: {total_gb - used_gb:.1f} GB")
                self.mem_bar.setValue(int(memory.percent))
                
            else:
                # Fallback to mock data if psutil is not available
                cpu_val = random.uniform(20, 80)
                self.cpu_percent_label.setText(f"{cpu_val:.1f}%")
                self.cpu_history.append(cpu_val)
                if len(self.cpu_history) > 30:
                    self.cpu_history.pop(0)
                
                self.cpu_cores_label.setText("8 cores")
                self.mem_total_label.setText("16.0 GB")
                self.mem_used_label.setText("Used: 8.2 GB")
                self.mem_free_label.setText("Free: 7.8 GB")
                self.mem_bar.setValue(random.randint(40, 80))
            
            # Update CPU graph
            self.cpu_graph.update()
            
        except Exception as e:
            logger.debug(f"Error updating system stats: {e}")
            # Use fallback values on error
            self.cpu_percent_label.setText("--")
            self.cpu_cores_label.setText("-- cores")
            self.mem_total_label.setText("-- GB")
            self.mem_used_label.setText("Used: -- GB")
            self.mem_free_label.setText("Free: -- GB")