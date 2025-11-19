"""
TitleBarWidget (Nebula UI)
With animated buttons and move/resize logic.
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame, QPushButton, QLineEdit, QMenu, QCheckBox
)
from PySide6.QtCore import Qt, QSize, Signal, QPoint, Slot
from PySide6.QtGui import QIcon, QAction, QColor, QPixmap
from ui.widgets.icon_utils import create_recolored_icon
import config

# --- NEW: Custom animated title bar button ---
class TitleBarButton(QPushButton):
    """Custom button to replicate macOS dots with hover/press animation"""
    def __init__(self, color, hover_icon_path=None, parent=None):
        super().__init__("", parent)
        self.setFixedSize(12, 12)
        
        # We will use QSS properties to store colors
        self.setProperty("baseColor", color)
        
        self.main_icon = None
        if hover_icon_path:
            # --- FIX: Use config.ICONS_DIR ---
            self.main_icon = QIcon(str(config.ICONS_DIR / hover_icon_path))
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 6px;
                border: 1px solid rgba(0, 0, 0, 0.2);
            }}
            QPushButton:hover {{
                background-color: {color};
                border: 1px solid rgba(255, 255, 255, 0.5);
            }}
            QPushButton:pressed {{
                background-color: {color};
                border: 1px solid rgba(255, 255, 255, 0.8);
            }}
        """)

    def enterEvent(self, event):
        """Show icon on hover"""
        if self.main_icon:
            self.setIcon(self.main_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide icon on leave"""
        self.setIcon(QIcon())
        super().leaveEvent(event)
# --- END NEW WIDGET ---

class TitleBarWidget(QFrame):
    # Signal for search functionality
    search_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(56) # 14 * 4 = 56px (h-14 in tailwind)
        
        # Store parent window for dragging
        self.parent_window = parent
        self.drag_start_position = None
        self.window_start_position = None
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)

        # 1. macOS-style dots (Now interactive buttons)
        dots_layout = QHBoxLayout()
        dots_layout.setSpacing(8)
        
        # We need to find simple 'close', 'minimize' icons
        # Assuming you've downloaded them to src/ui/assets/icons/
        self.close_btn = TitleBarButton("#ef4444", "close.svg") # Red with close icon
        self.min_btn = TitleBarButton("#eab308", "minimize.svg") # Yellow with minimize icon
        self.max_btn = TitleBarButton("#22c55e") # Green
        
        dots_layout.addWidget(self.close_btn)
        dots_layout.addWidget(self.min_btn)
        dots_layout.addWidget(self.max_btn)
        
        layout.addLayout(dots_layout)

        # 2. Logo/Title with proper spacing
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(8)
        
        # --- Point 2: Use kxw.svg (recolored to white) ---
        wolf_icon = QLabel()
        wolf_pixmap = QPixmap(str(config.ICONS_DIR / "kxw.svg"))
        wolf_icon.setPixmap(wolf_pixmap.scaled(
            QSize(28, 28), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

        # --- Point 1: Change name to "The Wolf VM" ---
        logo = QLabel("The Easy")
        logo.setObjectName("TitleBarLogo")
        subtitle = QLabel("VM")
        subtitle.setObjectName("TitleBarSubtitle")

        logo_layout.addWidget(wolf_icon)
        logo_layout.addWidget(logo)
        logo_layout.addWidget(subtitle)
        
        layout.addWidget(logo_container)
        layout.addSpacing(24)

        # 3. Global Search with overlaid icon
        search_container = QWidget()
        search_container.setFixedWidth(384)
        search_container.setFixedHeight(36)
        
        # Search input
        self.search = QLineEdit(search_container)
        self.search.setObjectName("GlobalSearch")
        self.search.setPlaceholderText("Search VMs, Snapshots, Settings...")
        self.search.setGeometry(0, 0, 384, 36)
        
        # Connect search functionality
        self.search.textChanged.connect(self._on_search_changed)
        
        # Search icon overlay
        search_icon = QLabel("🔍", search_container)
        search_icon.setGeometry(12, 8, 20, 20)
        search_icon.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 16px;
                background: transparent;
            }
        """)
        
        layout.addWidget(search_container)
        
        layout.addStretch()

        # 4. User/Settings Icons - Move snapshot and settings here like GG.html
        # self.notifications_btn = QPushButton("🔔")  # Bell icon
        # self.notifications_btn.setProperty("class", "GlassButton")
        # self.notifications_btn.setFixedSize(36, 36)

        # 4. User/Settings Icons with Setup Menu
        self.settings_btn = QPushButton()
        self.settings_btn.setProperty("class", "GlassButton")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setIcon(create_recolored_icon(str(config.ICONS_DIR / "gear.svg"), QColor("#e2e8f0")))

        # Create the setup menu
        self.setup_menu = QMenu(self)
        # self.settings_btn.setMenu(self.setup_menu) # <-- REMOVED to hide arrow
        self.settings_btn.clicked.connect(self._show_setup_menu) # <-- ADDED

        # --- TASK 1.1 MODIFICATION ---
        # Add actions
        self.setup_sudo_action = QAction("1. Configure Sudo Permissions...", self)
        self.setup_lg_action = QAction("2. Install Looking Glass Client...", self)

        self.setup_menu.addAction(self.setup_sudo_action)
        self.setup_menu.addAction(self.setup_lg_action)
        self.setup_menu.addSeparator()
        
        # --- TASK 2.1 MODIFICATION ---
        self.app_settings_action = QAction("VM Settings...", self)
        self.app_settings_action.setEnabled(False) # Will be enabled by main_window
        self.setup_menu.addAction(self.app_settings_action)
        # --- END MODIFICATION ---

        user_avatar = QLabel()
        user_avatar.setFixedSize(32, 32)
        user_avatar.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                          stop:0 #6366f1, stop:1 #a855f7);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
        """)
        
        layout.addWidget(self.settings_btn)
        layout.addWidget(user_avatar)
        
        # Connect window control buttons
        self.close_btn.clicked.connect(self._close_window)
        self.min_btn.clicked.connect(self._minimize_window)
        self.max_btn.clicked.connect(self._toggle_maximize)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging"""
        if event.button() == Qt.LeftButton and self.parent_window:
            self.drag_start_position = event.globalPosition().toPoint()
            self.window_start_position = self.parent_window.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging"""
        if (event.buttons() == Qt.LeftButton and 
            self.drag_start_position is not None and 
            self.parent_window):
            
            # Calculate the distance moved
            delta = event.globalPosition().toPoint() - self.drag_start_position
            
            # Move the window
            new_pos = self.window_start_position + delta
            self.parent_window.move(new_pos)
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

    def _close_window(self):
        """Close the parent window"""
        if self.parent_window:
            self.parent_window.close()

    def _minimize_window(self):
        """Minimize the parent window"""
        if self.parent_window:
            self.parent_window.showMinimized()

    def _toggle_maximize(self):
        """Toggle maximize/restore the parent window"""
        if self.parent_window:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
            else:
                self.parent_window.showMaximized()
    
    def _on_search_changed(self, text):
        """Handle search text changes"""
        self.search_changed.emit(text.lower().strip())

    @Slot()
    def _show_setup_menu(self):
        """Manually shows the setup menu without attaching it to the button."""
        menu_pos = self.settings_btn.mapToGlobal(QPoint(0, self.settings_btn.height()))
        self.setup_menu.exec(menu_pos)