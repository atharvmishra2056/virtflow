"""
SidebarWidget (Nebula UI)
This replaces the old VMListWidget and holds the core logic
for managing the VM list.
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QPushButton, QListWidgetItem,
    QMessageBox, QMenu
)
# --- TASK 1.4: Import QThread ---
from PySide6.QtCore import Qt, QSize, Signal, QTimer, Slot, QThread

from PySide6.QtGui import QIcon, QAction, QCursor, QColor

# Import our new custom item widget
from ui.widgets.vm_list_item_widget import VMListItemWidget
from ui.widgets.icon_utils import create_recolored_icon

from backend.libvirt_manager import LibvirtManager
from backend.vm_controller import VMController, VMState
# --- TASK 1.4: Import GuestDriverHelper ---
from backend.guest_driver_helper import GuestDriverHelper
from models.vm_model import VMModel
from utils.logger import logger
import config
import time

# --- TASK 1.4: Worker thread for Guest Tools ---
class GuestToolsWorker(QThread):
    """Worker thread for installing guest tools"""
    finished = Signal(bool, str) # success, message
    
    def __init__(self, helper: GuestDriverHelper, vm_name: str):
        super().__init__()
        self.helper = helper
        self.vm_name = vm_name
        
    def run(self):
        try:
            success, message = self.helper.install_virtio_drivers(self.vm_name)
            self.finished.emit(success, message)
        except Exception as e:
            logger.exception(f"Exception in GuestToolsWorker: {e}")
            self.finished.emit(False, str(e))
# --- END TASK 1.4 ---

class SidebarWidget(QFrame):
    """Sidebar holding the VM list and New VM button"""
    
    # Signal: Emits (VMModel, stats_dict)
    # Emits None if no VM is selected
    vm_selected = Signal(object, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(288) # w-72
        
        # --- Backend ---
        self.manager = LibvirtManager()
        self.controller = VMController(self.manager)
        # --- TASK 1.4: Instantiate helper ---
        self.guest_helper = GuestDriverHelper(self.manager)
        self.vm_data = {} # Cache for VMModel objects by UUID
        self.prev_stats = {}
        self.prev_time = {}
        # --- TASK 1.4: Add worker attribute ---
        self._guest_tools_worker = None

        # --- UI ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16) # p-4
        self.main_layout.setSpacing(12)

        self.title = QLabel("YOUR MACHINES")
        self.title.setObjectName("SidebarTitle")
        
        self.vm_list = QListWidget()
        self.vm_list.setObjectName("VMList")
        self.vm_list.itemSelectionChanged.connect(self._on_selection_changed)
        
        # --- NEW: Add Context Menu ---
        self.vm_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.vm_list.customContextMenuRequested.connect(self.show_vm_context_menu)
        # --- END NEW ---

        self.new_vm_btn = QPushButton(" Create New VM")
        self.new_vm_btn.setObjectName("NewVMButton")
        # The "New VM" button is a PrimaryButton, which has white text.
        # We need a white icon to match.
        plus_icon = create_recolored_icon(str(config.ICONS_DIR / "plus-circle.svg"), QColor("#FFFFFF"))
        self.new_vm_btn.setIcon(plus_icon)
        # self.new_vm_btn.clicked.connect(...) # We'll connect this later

        self.main_layout.addWidget(self.title)
        self.main_layout.addWidget(self.vm_list, 1) # 1 = stretch
        self.main_layout.addWidget(self.new_vm_btn)
        
        # --- Timer ---
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_vm_list)
        self.refresh_timer.start(1000) # Refresh every 1 second
        
        # Store original VM list for filtering
        self.all_vms = []
        self.current_filter = ""
        
        self.refresh_vm_list()

    def _get_selected_uuid(self):
        """Gets the UUID of the currently selected item"""
        selected_items = self.vm_list.selectedItems()
        if not selected_items:
            return None
        # Get data from the QListWidgetItem
        return selected_items[0].data(Qt.UserRole)

    def _get_selected_domain(self):
        """Gets the libvirt domain for the selected VM"""
        uuid = self._get_selected_uuid()
        if not uuid:
            return None
        
        try:
            domain = self.manager.get_vm_by_uuid(uuid)
            if not domain:
                logger.warning(f"Could not find domain for UUID {uuid}")
            return domain
        except Exception as e:
            logger.error(f"Error getting domain by UUID: {e}")
            return None

    def refresh_vm_list(self):
        """Refreshes the VM list from libvirt"""
        try:
            domains = self.manager.list_all_vms()
            
            try:
                self.vm_list.itemSelectionChanged.disconnect(self._on_selection_changed)
            except RuntimeError:
                pass 

            current_uuid = self._get_selected_uuid()
            
            refreshed_uuids = set()
            new_vm_data = {}

            for domain in domains:
                info = self.controller.get_vm_info(domain)
                if not info:
                    continue
                
                vm = VMModel.from_libvirt_info(info)
                new_vm_data[vm.uuid] = vm
                refreshed_uuids.add(vm.uuid)

                list_item = self._find_item_by_uuid(vm.uuid)
                
                if list_item:
                    widget = self.vm_list.itemWidget(list_item)
                    if widget:
                        widget.update_data(vm)
                else:
                    self._add_vm_to_list(vm)
            
            items_to_remove = []
            for i in range(self.vm_list.count()):
                item = self.vm_list.item(i)
                uuid = item.data(Qt.UserRole)
                if uuid not in refreshed_uuids:
                    items_to_remove.append(item)
            
            for item in items_to_remove:
                self.vm_list.takeItem(self.vm_list.row(item))

            self.vm_data = new_vm_data
            
            if current_uuid:
                self._select_item_by_uuid(current_uuid)
            
            self.vm_list.itemSelectionChanged.connect(self._on_selection_changed)
            
            # Manually trigger update for stats
            self._on_selection_changed()

        except Exception as e:
            # This can happen if libvirt connection is lost
            logger.error(f"Failed to refresh VM list: {e}")
            # Optionally, you could stop the timer here
            # self.refresh_timer.stop()
        
        # Store all VMs for filtering
        # self.all_vms = domains # domains is not defined here if exception
        
        # Apply current filter if any
        if self.current_filter:
            self._apply_filter(self.current_filter)

    def _add_vm_to_list(self, vm: VMModel):
        """Adds a new VM to the QListWidget with the custom widget"""
        list_item = QListWidgetItem(self.vm_list)
        list_item.setData(Qt.UserRole, vm.uuid)
        
        item_widget = VMListItemWidget(vm)
        list_item.setSizeHint(item_widget.sizeHint())
        
        self.vm_list.addItem(list_item)
        self.vm_list.setItemWidget(list_item, item_widget)

    def _find_item_by_uuid(self, uuid: str) -> QListWidgetItem | None:
        """Finds a QListWidgetItem by its stored UUID"""
        for i in range(self.vm_list.count()):
            item = self.vm_list.item(i)
            if item.data(Qt.UserRole) == uuid:
                return item
        return None
    
    def _select_item_by_uuid(self, uuid: str):
        """Selects a list item by its UUID"""
        item = self._find_item_by_uuid(uuid)
        if item:
            self.vm_list.blockSignals(True)
            self.vm_list.setCurrentItem(item)
            self.vm_list.blockSignals(False)

    def _on_selection_changed(self):
        """Emits the selected VM's data and stats"""
        uuid = self._get_selected_uuid()
        
        if not uuid or uuid not in self.vm_data:
            self.vm_selected.emit(None, {}) # Emit empty data
            return
            
        vm = self.vm_data[uuid]
        
        # Calculate stats
        stats = {}
        if vm.state == VMState.RUNNING:
            current_time = time.time()
            if uuid in self.prev_stats:
                time_delta = current_time - self.prev_time.get(uuid, current_time)
                if time_delta > 0:
                    stats['disk_read'] = (vm.disk_read_bytes - self.prev_stats[uuid]['disk_read_bytes']) / time_delta
                    stats['disk_write'] = (vm.disk_write_bytes - self.prev_stats[uuid]['disk_write_bytes']) / time_delta
                    stats['net_rx'] = (vm.net_rx_bytes - self.prev_stats[uuid]['net_rx_bytes']) / time_delta
                    stats['net_tx'] = (vm.net_tx_bytes - self.prev_stats[uuid]['net_tx_bytes']) / time_delta

            stats = {k: max(0, v) for k, v in stats.items()} # Clamp negatives
            
            # Store current stats for next calculation
            self.prev_stats[uuid] = {
                'disk_read_bytes': vm.disk_read_bytes,
                'disk_write_bytes': vm.disk_write_bytes,
                'net_rx_bytes': vm.net_rx_bytes,
                'net_tx_bytes': vm.net_tx_bytes
            }
            self.prev_time[uuid] = current_time
        else:
             # Clear old stats if VM is off
            if uuid in self.prev_stats: del self.prev_stats[uuid]
            if uuid in self.prev_time: del self.prev_time[uuid]
        
        self.vm_selected.emit(vm, stats)

    # --- SLOTS FOR BUTTONS IN MAIN STAGE ---
    
    def on_start_stop_vm(self):
        """Called when the main start/stop button is clicked"""
        domain = self._get_selected_domain()
        if not domain:
            return
            
        if domain.isActive():
            # Stop the VM
            reply = QMessageBox.question(
                self, "Confirm Stop",
                f"Shutdown VM '{domain.name()}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.controller.stop_vm_and_close_viewer(domain)
        else:
            # Start the VM
            # We will run this in a thread like before to prevent UI freeze
            from PySide6.QtCore import QThread, Signal
            
            class VMStartWorker(QThread):
                finished = Signal(bool, str)
                
                def __init__(self, controller, domain):
                    super().__init__()
                    self.controller = controller
                    self.domain = domain
                
                def run(self):
                    try:
                        success = self.controller.start_vm_with_viewer(self.domain)
                        self.finished.emit(success, "")
                    except Exception as e:
                        logger.exception(f"Failed to start VM: {e}")
                        self.finished.emit(False, str(e))
            
            def on_start_finished(success, error):
                if not success:
                    QMessageBox.critical(self, "Error", f"Failed to start VM:\n{error}")
                self.refresh_vm_list()

            self._start_worker = VMStartWorker(self.controller, domain)
            self._start_worker.finished.connect(on_start_finished)
            self._start_worker.start()
        
        self.refresh_vm_list()

    def on_pause_vm(self):
        domain = self._get_selected_domain()
        if not domain:
            return
        
        if domain.state()[0] == VMState.RUNNING:
            self.controller.pause_vm(domain)
        elif domain.state()[0] == VMState.PAUSED:
            self.controller.resume_vm(domain)
        
        self.refresh_vm_list()

    def on_reboot_vm(self):
        domain = self._get_selected_domain()
        if not domain:
            return
        
        if domain.isActive():
            reply = QMessageBox.question(
                self, "Confirm Reboot",
                f"Reboot VM '{domain.name()}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.controller.reboot_vm(domain)
                self.refresh_vm_list()
    
    def filter_vms(self, search_text):
        """Filter VMs based on search text"""
        self.current_filter = search_text
        self._apply_filter(search_text)
    
    def _apply_filter(self, search_text):
        """Apply the filter to the VM list"""
        if not search_text:
            # Show all items
            for i in range(self.vm_list.count()):
                item = self.vm_list.item(i)
                item.setHidden(False)
            return
        
        # Filter items
        for i in range(self.vm_list.count()):
            item = self.vm_list.item(i)
            widget = self.vm_list.itemWidget(item)
            
            if widget and hasattr(widget, 'vm'):
                vm_name = widget.vm.name.lower()
                vm_state = widget.vm.state_name.lower()
                
                # Check if search text matches name or state
                matches = (search_text in vm_name or 
                          search_text in vm_state or
                          search_text in "vm" or
                          search_text in "machine")
                
                item.setHidden(not matches)
            else:
                item.setHidden(True)
    
    # --- NEW: Context Menu ---
    @Slot()
    def show_vm_context_menu(self, pos):
        item = self.vm_list.itemAt(pos)
        if not item:
            return

        domain = self._get_selected_domain()
        if not domain:
            return
            
        vm = self.vm_data[domain.UUIDString()]

        menu = QMenu(self)
        
        # --- Display Preference ---
        display_menu = menu.addMenu("Display Preference")
        
        spice_action = QAction("SPICE (Smooth, High-Latency)", self)
        spice_action.setCheckable(True)
        
        lg_action = QAction("Looking Glass (Fast, Low-Lag)", self)
        lg_action.setCheckable(True)

        # Check the currently saved preference
        current_pref = self.manager.get_display_preference(domain)
        if current_pref == "looking-glass":
            lg_action.setChecked(True)
        else:
            spice_action.setChecked(True)

        # Connect signals
        spice_action.triggered.connect(lambda: self.on_set_display_pref(domain, "spice"))
        lg_action.triggered.connect(lambda: self.on_set_display_pref(domain, "looking-glass"))
        
        display_menu.addAction(spice_action)
        display_menu.addAction(lg_action)
        
        # --- Guest Tools ---
        menu.addSeparator()
        tools_action = QAction("Install/Update Guest Tools", self)
        tools_action.setEnabled(vm.state == VMState.RUNNING)
        # --- TASK 1.4: Connect to new worker slot ---
        tools_action.triggered.connect(self._on_install_guest_tools)
        if vm.state != VMState.RUNNING:
            tools_action.setToolTip("VM must be running to install guest tools")
        # --- END TASK 1.4 ---
        menu.addAction(tools_action)
        
        menu.exec(self.vm_list.mapToGlobal(pos))

    @Slot()
    def on_set_display_pref(self, domain, preference):
        """Slot to save the display preference."""
        self.manager.set_display_preference(domain, preference)
        logger.info(f"Set display preference for {domain.name()} to {preference}")

    # --- TASK 1.4: Updated Slot ---
    @Slot()
    def _on_install_guest_tools(self):
        """Slot to trigger guest tools installation."""
        domain = self._get_selected_domain()
        if not domain:
            return
            
        if self._guest_tools_worker and self._guest_tools_worker.isRunning():
            QMessageBox.warning(self, "In Progress", "Guest tools installation is already running.")
            return

        logger.info(f"Attempting to install guest tools for {domain.name()}...")
        
        self._guest_tools_worker = GuestToolsWorker(self.guest_helper, domain.name())
        self._guest_tools_worker.finished.connect(self._on_guest_tools_finished)
        self._guest_tools_worker.start()
        
        QMessageBox.information(self, "Guest Tools",
            f"Attempting to install VirtIO guest tools in {domain.name()}...\n\n"
            "This may take a few moments. You will be notified when it's complete.")

    @Slot(bool, str)
    def _on_guest_tools_finished(self, success: bool, message: str):
        """Slot to handle completion of the guest tools worker thread."""
        if success:
            QMessageBox.information(self, "Guest Tools Installation", message)
        else:
            QMessageBox.critical(self, "Guest Tools Installation Failed", message)
    # --- END TASK 1.4 ---