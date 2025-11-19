"""
SettingsDialog (HyperGlass UI - Phase 2 Redux)
High-fidelity replica of xyz.html
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QGraphicsBlurEffect, QScrollArea,
    QButtonGroup, QTreeWidget, QTreeWidgetItem, QAbstractButton,
    QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QSize, Signal, Slot
from PySide6.QtGui import QIcon, QColor, QFont

from backend.libvirt_manager import LibvirtManager
from models.vm_model import VMModel
from utils.logger import logger
import config

# --- FIX: Import GlassToggle, remove IOSSwitch ---
from ui.widgets.hyperglass_widgets import (
    GlassInput, GlassSlider, GlassSelect, GlassCard,
    SidebarButton, PanelHeader, GlassToggle
)
# from ui.widgets.ios_switch import IOSSwitch # <-- Removed

# Helper function to load QSS
def load_qss(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Could not load QSS file: {path}")
        return ""

class SettingsDialog(QDialog):
    
    def __init__(self, vm: VMModel, manager: LibvirtManager, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.manager = manager
        self.domain = self.manager.get_vm_by_uuid(vm.uuid) # Get libvirt domain
        
        self.setWindowTitle("HyperGlass VM Settings")
        self.setObjectName("HyperGlassDialog")
        self.setMinimumSize(1024, 768) # 90vw max-w-6xl h-[85vh]
        self.setModal(True)
        
        # --- Real Glass Effect (Point 4) ---
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        # We blur the parent window's background, not this dialog
        # This simulates the "backdrop-filter"
        self.parent().enable_blur()
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main Glass Frame
        self.glass_frame = QFrame(self)
        self.glass_frame.setObjectName("HyperGlassFrame")
        self.frame_layout = QVBoxLayout(self.glass_frame)
        self.frame_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_layout.setSpacing(0)
        
        # --- 1. Custom Title Bar ---
        self.title_bar = self._create_title_bar()
        self.frame_layout.addWidget(self.title_bar)

        # --- 2. Body Layout (Sidebar + Content) ---
        self.body_layout = QHBoxLayout()
        self.body_layout.setSpacing(0)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 2a. Sidebar (Full 8 items) ---
        self.sidebar = self._create_sidebar()
        self.body_layout.addWidget(self.sidebar)
        
        # --- 2b. Content Area ---
        self.content_stack = QStackedWidget(self)
        self.content_stack.setObjectName("ContentStack")
        self.body_layout.addWidget(self.content_stack, 1)

        # Create all panels from xyz.html
        self.content_stack.addWidget(self._create_panel_general())
        self.content_stack.addWidget(self._create_panel_system())
        self.content_stack.addWidget(self._create_panel_display())
        self.content_stack.addWidget(self._create_panel_storage())
        self.content_stack.addWidget(self._create_panel_placeholder("Audio", "speaker-high"))
        self.content_stack.addWidget(self._create_panel_placeholder("Network", "globe"))
        self.content_stack.addWidget(self._create_panel_placeholder("Shared Folders", "folder-open"))
        self.content_stack.addWidget(self._create_panel_placeholder("USB", "usb"))
        
        self.frame_layout.addLayout(self.body_layout, 1)
        self.main_layout.addWidget(self.glass_frame)
        
        # Apply our new QSS
        self.setStyleSheet(load_qss(config.BASE_DIR / "ui" / "styles" / "hyperglass.qss"))
        
        # Connect signals
        self.sidebar_group.buttonClicked.connect(self._on_sidebar_nav)
        self.btn_general.setChecked(True) # Set initial page
        
        # Load settings
        self._load_settings()

    def showEvent(self, event):
        """Enable blur when dialog is shown"""
        super().showEvent(event)
        # Get the main window and enable blur
        main_window = self.parent()
        if hasattr(main_window, 'enable_blur'):
            main_window.enable_blur()

    def reject(self):
        """Disable blur and close dialog"""
        main_window = self.parent()
        if hasattr(main_window, 'disable_blur'):
            main_window.disable_blur()
        super().reject()

    def accept(self):
        """Save settings, disable blur, and close dialog"""
        self._on_apply_changes()
        main_window = self.parent()
        if hasattr(main_window, 'disable_blur'):
            main_window.disable_blur()
        super().accept()

    def _create_title_bar(self) -> QFrame:
        """Creates the custom title bar from xyz.html"""
        title_bar = QFrame(self)
        title_bar.setObjectName("SettingsTitleBar")
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        # VM Info
        vm_name_label = QLabel(self.vm.name)
        vm_name_label.setObjectName("VmNameLabel")
        vm_status_label = QLabel(self.vm.state_name.upper())
        vm_status_label.setObjectName("VmStatusLabel")
        vm_status_label.setProperty("status", "running" if self.vm.is_active else "stopped")
        
        layout.addWidget(vm_name_label)
        layout.addWidget(vm_status_label)
        layout.addStretch()
        
        # Buttons
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("class", "GlassButton")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.setProperty("class", "PrimaryButton")
        self.apply_btn.clicked.connect(self.accept)
        
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.apply_btn)
        
        return title_bar

    def _create_sidebar(self) -> QFrame:
        """Creates the left navigation sidebar from xyz.html"""
        sidebar = QFrame(self)
        sidebar.setObjectName("SettingsSidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)
        
        self.sidebar_group = QButtonGroup(self)
        self.sidebar_group.setExclusive(True)
        
        hardware_label = QLabel("Hardware")
        hardware_label.setProperty("class", "SidebarHeader")
        layout.addWidget(hardware_label)
        
        self.btn_general = SidebarButton("gear.svg", "General")
        self.btn_system = SidebarButton("cpu.svg", "System")
        self.btn_display = SidebarButton("monitor.svg", "Display")
        self.btn_storage = SidebarButton("hard-drives.svg", "Storage")
        self.btn_audio = SidebarButton("speaker-high.svg", "Audio")
        self.btn_network = SidebarButton("globe.svg", "Network")
        
        self.sidebar_group.addButton(self.btn_general, 0)
        self.sidebar_group.addButton(self.btn_system, 1)
        self.sidebar_group.addButton(self.btn_display, 2)
        self.sidebar_group.addButton(self.btn_storage, 3)
        self.sidebar_group.addButton(self.btn_audio, 4)
        self.sidebar_group.addButton(self.btn_network, 5)
        
        layout.addWidget(self.btn_general)
        layout.addWidget(self.btn_system)
        layout.addWidget(self.btn_display)
        layout.addWidget(self.btn_storage)
        layout.addWidget(self.btn_audio)
        layout.addWidget(self.btn_network)
        
        integration_label = QLabel("Integration")
        integration_label.setProperty("class", "SidebarHeader")
        layout.addWidget(integration_label)
        
        self.btn_shared = SidebarButton("folder-open.svg", "Shared Folders")
        self.btn_usb = SidebarButton("usb.svg", "USB")
        
        self.sidebar_group.addButton(self.btn_shared, 6)
        self.sidebar_group.addButton(self.btn_usb, 7)
        
        layout.addWidget(self.btn_shared)
        layout.addWidget(self.btn_usb)
        
        layout.addStretch()
        return sidebar

    def _create_scroll_area(self, widget: QWidget) -> QScrollArea:
        """Helper to create a styled scroll area for a panel"""
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(widget)
        # Style is applied from nebula.qss QAbstractScrollArea
        return scroll

    # --- FIX: Point 4 - Helper for new toggle ---
    def _create_toggle_row(self, title: str, subtitle: str) -> (QWidget, QCheckBox):
        """Helper to create a standard row with title, subtitle, and toggle."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.addWidget(QLabel(title, objectName="CardTitle"))
        text_layout.addWidget(QLabel(subtitle, objectName="CardSubtitle"))
        
        toggle = GlassToggle() # Use the new QSS-based toggle
        
        row_layout.addLayout(text_layout)
        row_layout.addStretch()
        row_layout.addWidget(toggle)
        return row, toggle
    # --- END FIX ---

    def _create_panel_general(self) -> QWidget:
        panel = QFrame()
        panel.setProperty("class", "SettingsPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        
        layout.addWidget(PanelHeader("General Settings", "Basic configuration for this virtual machine."))
        
        # Card 1: Main Config
        card1 = GlassCard()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setSpacing(12)
        
        card1_layout.addWidget(QLabel("VM Name", objectName="CardTitle"))
        self.general_vm_name = GlassInput(self.vm.name)
        card1_layout.addWidget(self.general_vm_name)
        
        card1_layout.addWidget(QLabel("OS Type", objectName="CardTitle"))
        self.general_os_type = GlassSelect()
        self.general_os_type.addItems(["Microsoft Windows", "Linux", "macOS"])
        card1_layout.addWidget(self.general_os_type)
        layout.addWidget(card1)
        
        # Card 2: Toggles
        card2 = GlassCard()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(12)
        
        # --- FIX: Point 4 ---
        clipboard_row, self.general_clipboard_toggle = self._create_toggle_row("Shared Clipboard", "Allow copying text between host and guest.")
        tpm_row, self.general_tpm_toggle = self._create_toggle_row("Enable TPM 2.0", "Required for Windows 11.")
        
        card2_layout.addWidget(clipboard_row)
        card2_layout.addWidget(tpm_row)
        # --- END FIX ---
        layout.addWidget(card2)
        
        layout.addStretch()
        return self._create_scroll_area(panel)

    def _create_panel_system(self) -> QWidget:
        panel = QFrame()
        panel.setProperty("class", "SettingsPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        
        layout.addWidget(PanelHeader("System Resources", "Motherboard, Processor, and Memory."))
        
        # Card 1: Base Memory
        card_ram = GlassCard()
        ram_layout = QVBoxLayout(card_ram)
        ram_layout.setSpacing(8)
        
        ram_header_layout = QHBoxLayout()
        ram_header_layout.addWidget(QLabel("Base Memory", objectName="CardTitle"))
        ram_header_layout.addStretch()
        self.system_ram_label = QLabel(f"{self.vm.max_memory_mb} MB")
        self.system_ram_label.setStyleSheet("font-size: 16px; font-weight: 500;")
        ram_header_layout.addWidget(self.system_ram_label)
        
        self.system_ram_slider = GlassSlider()
        self.system_ram_slider.setRange(1024, 32768) # 1GB to 32GB
        self.system_ram_slider.setSingleStep(1024)
        self.system_ram_slider.setPageStep(1024)
        self.system_ram_slider.setValue(self.vm.max_memory_mb)
        self.system_ram_slider.valueChanged.connect(
            lambda v: self.system_ram_label.setText(f"{v} MB")
        )
        
        ram_layout.addLayout(ram_header_layout)
        ram_layout.addWidget(self.system_ram_slider)
        ram_layout.addWidget(QLabel("Host Memory: 32768 MB", objectName="CardSubtitle"))
        layout.addWidget(card_ram)

        # Card 2: Processors
        card_cpu = GlassCard()
        cpu_layout = QVBoxLayout(card_cpu)
        cpu_layout.setSpacing(8)
        
        cpu_header_layout = QHBoxLayout()
        cpu_header_layout.addWidget(QLabel("Processors", objectName="CardTitle"))
        cpu_header_layout.addStretch()
        self.system_cpu_label = QLabel(f"{self.vm.vcpus} CPUs")
        self.system_cpu_label.setStyleSheet("font-size: 16px; font-weight: 500;")
        cpu_header_layout.addWidget(self.system_cpu_label)
        
        self.system_cpu_slider = GlassSlider()
        self.system_cpu_slider.setRange(1, 16) # Host CPUs
        self.system_cpu_slider.setValue(self.vm.vcpus)
        self.system_cpu_slider.valueChanged.connect(
            lambda v: self.system_cpu_label.setText(f"{v} CPUs")
        )
        
        cpu_layout.addLayout(cpu_header_layout)
        cpu_layout.addWidget(self.system_cpu_slider)
        cpu_layout.addWidget(QLabel("Host Cores: 16", objectName="CardSubtitle"))
        layout.addWidget(card_cpu)
        
        # Card 3: Performance Toggles (from old plan)
        card_perf = GlassCard()
        perf_layout = QVBoxLayout(card_perf)
        
        # --- FIX: Point 4 ---
        cpu_pin_row, self.sys_cpu_pinning_toggle = self._create_toggle_row("Enable CPU Pinning", "Improves performance, reduces stutter.")
        hugepages_row, self.sys_hugepages_toggle = self._create_toggle_row("Enable HugePages", "Reduces memory overhead.")
        perf_layout.addWidget(cpu_pin_row)
        perf_layout.addWidget(hugepages_row)
        # --- END FIX ---
        layout.addWidget(card_perf)
        
        layout.addStretch()
        return self._create_scroll_area(panel)

    def _create_panel_display(self) -> QWidget:
        panel = QFrame()
        panel.setProperty("class", "SettingsPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        
        layout.addWidget(PanelHeader("Display", "Graphics controller, VRAM, and optimizations."))
        
        # Card 1: VRAM
        card_vram = GlassCard()
        vram_layout = QVBoxLayout(card_vram)
        vram_header = QHBoxLayout()
        vram_header.addWidget(QLabel("Video Memory", objectName="CardTitle"))
        vram_header.addStretch()
        self.display_vram_label = QLabel("128 MB")
        self.display_vram_label.setStyleSheet("font-size: 16px; font-weight: 500;")
        vram_header.addWidget(self.display_vram_label)
        
        self.display_vram_slider = GlassSlider()
        self.display_vram_slider.setRange(64, 256)
        self.display_vram_slider.setValue(128)
        self.display_vram_slider.valueChanged.connect(
            lambda v: self.display_vram_label.setText(f"{v} MB")
        )
        
        vram_layout.addLayout(vram_header)
        vram_layout.addWidget(self.display_vram_slider)
        vram_layout.addWidget(QLabel("For QXL/VirtIO GPU", objectName="CardSubtitle"))
        card_vram.setLayout(vram_layout)
        layout.addWidget(card_vram)
        
        # Card 2: Toggles
        card_toggles = GlassCard()
        toggles_layout = QVBoxLayout(card_toggles)
        
        # --- FIX: Point 4 ---
        spice_row, self.display_spice_gl_toggle = self._create_toggle_row("SPICE OpenGL", "Use OpenGL for faster 2D rendering")
        accel_row, self.display_3d_accel_toggle = self._create_toggle_row("Enable 3D Acceleration", "Pass through OpenGL/DirectX (VirGL)")

        toggles_layout.addWidget(spice_row)
        toggles_layout.addWidget(accel_row)
        # --- END FIX ---
        card_toggles.setLayout(toggles_layout)
        layout.addWidget(card_toggles)
        
        layout.addStretch()
        return self._create_scroll_area(panel)

    def _create_panel_storage(self) -> QWidget:
        panel = QFrame()
        panel.setProperty("class", "SettingsPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        
        layout.addWidget(PanelHeader("Storage Devices", "Controller hierarchy and disk images."))
        
        # This is a placeholder for the tree layout
        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(QLabel("Storage Tree (WIP)", objectName="CardTitle"))
        card_layout.addWidget(QLabel("This will show the SATA/NVMe controllers and attached disks, as seen in xyz.html.", objectName="CardSubtitle"))
        layout.addWidget(card)
        
        layout.addStretch()
        return self._create_scroll_area(panel)

    def _create_panel_placeholder(self, title: str, icon: str) -> QWidget:
        """Creates a placeholder panel for unimplemented sections"""
        panel = QFrame()
        panel.setProperty("class", "SettingsPanel")
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignCenter)
        
        icon_label = QLabel()
        # icon_label.setPixmap(QIcon(str(config.ICONS_DIR / f"{icon}.svg")).pixmap(64, 64))
        icon_label.setText(icon) # Placeholder
        icon_label.setStyleSheet("font-size: 64px; color: rgba(255, 255, 255, 0.3);")
        
        title_label = QLabel(f"{title} Settings")
        title_label.setProperty("class", "PanelTitle")
        
        sub_label = QLabel("This section will be implemented in a future phase.")
        sub_label.setProperty("class", "PanelSubtitle")
        
        layout.addWidget(icon_label, 0, Qt.AlignCenter)
        layout.addWidget(title_label, 0, Qt.AlignCenter)
        layout.addWidget(sub_label, 0, Qt.AlignCenter)
        
        return self._create_scroll_area(panel)

    @Slot(QAbstractButton)
    def _on_sidebar_nav(self, button: QPushButton):
        """Switches the content panel"""
        index = self.sidebar_group.id(button)
        if index is not None:
            self.content_stack.setCurrentIndex(index)

    def _load_settings(self):
        """Load existing VM settings from XML metadata"""
        if not self.domain:
            logger.warning(f"No domain for {self.vm.uuid}, cannot load settings.")
            return
            
        settings = self.manager.get_all_vm_settings(self.domain)
        
        # General
        self.general_vm_name.setText(self.vm.name) # VM name is from info
        self.general_tpm_toggle.setChecked(
            settings.get("tpm_enabled", "false").lower() == "true"
        )
        
        # System
        self.system_ram_slider.setValue(self.vm.max_memory_mb)
        self.system_cpu_slider.setValue(self.vm.vcpus)
        self.sys_cpu_pinning_toggle.setChecked(
            settings.get("cpu_pinning", "false").lower() == "true"
        )
        self.sys_hugepages_toggle.setChecked(
            settings.get("hugepages", "false").lower() == "true"
        )
        
        # Display
        spice_gl = settings.get("spice_opengl", "false").lower() == "true"
        self.display_spice_gl_toggle.setChecked(spice_gl)
        self.display_3d_accel_toggle.setChecked(
            settings.get("3d_accel", "false").lower() == "true"
        )
        vram = int(settings.get("vram", "128"))
        self.display_vram_slider.setValue(vram)

    def _on_apply_changes(self):
        """Save all settings to libvirt XML"""
        if not self.domain:
            logger.error("Cannot apply settings: VM domain not found.")
            return
        
        from PySide6.QtWidgets import QMessageBox
        
        if self.domain.isActive():
            QMessageBox.warning(self, "VM is Running",
                "Core hardware settings (RAM, CPU, Name, TPM) can only be changed when the VM is shut off. "
                "Other settings (like performance toggles) will be applied on the next restart.")
        
        logger.info(f"Applying settings for VM {self.vm.name}...")

        # --- 1. Apply Core Hardware (RAM, CPU, Name, TPM) ---
        # These can only be changed while VM is OFF
        if not self.domain.isActive():
            try:
                new_ram = self.system_ram_slider.value()
                new_vcpus = self.system_cpu_slider.value()
                
                # Update RAM/CPU
                success = self.manager.update_core_hardware(self.domain, new_vcpus, new_ram)
                if not success:
                    raise RuntimeError("Failed to update core XML for RAM/CPU.")
                    
                # Update Name
                new_name = self.general_vm_name.text()
                if new_name != self.vm.name:
                    self.domain.rename(new_name)
                
                # Update TPM (Requires full re-define)
                # This is a simplified add/remove
                tpm_enabled = self.general_tpm_toggle.isChecked()
                self.manager.set_vm_setting(self.domain, "tpm_enabled", "true" if tpm_enabled else "false")

            except Exception as e:
                logger.error(f"Failed to apply core hardware settings: {e}")
                QMessageBox.critical(self, "Error", f"Failed to apply core settings: {e}")
                return # Stop apply
        
        # --- 2. Apply Metadata Settings (for next run) ---
        
        # System (Performance Toggles)
        self.manager.set_vm_setting(
            self.domain, 
            "cpu_pinning", 
            "true" if self.sys_cpu_pinning_toggle.isChecked() else "false"
        )
        self.manager.set_vm_setting(
            self.domain, 
            "hugepages", 
            "true" if self.sys_hugepages_toggle.isChecked() else "false"
        )
        
        # Display
        self.manager.set_vm_setting(
            self.domain, 
            "spice_opengl", 
            "true" if self.display_spice_gl_toggle.isChecked() else "false"
        )
        self.manager.set_vm_setting(
            self.domain, 
            "3d_accel", 
            "true" if self.display_3d_accel_toggle.isChecked() else "false"
        )
        self.manager.set_vm_setting(
            self.domain,
            "vram",
            str(self.display_vram_slider.value())
        )
        
        logger.info("All settings applied.")
        # self.accept() is called by the original apply_btn connection