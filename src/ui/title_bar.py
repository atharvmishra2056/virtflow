"""
TitleBarWidget (Nebula UI)
With animated buttons and move/resize logic.
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame, QPushButton, QLineEdit
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
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
            self.main_icon = QIcon(str(config.BASE_DIR / hover_icon_path))
        
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
        self.close_btn = TitleBarButton("#ef4444") # Red
        self.min_btn = TitleBarButton("#eab308") # Yellow
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
        
        # Cube icon (using emoji for now, can be replaced with SVG)
        cube_icon = QLabel("🧊")
        cube_icon.setStyleSheet("""
            QLabel {
                color: #6366f1;
                font-size: 20px;
            }
        """)
        
        logo = QLabel("NEBULA")
        logo.setObjectName("TitleBarLogo")
        subtitle = QLabel("VM")
        subtitle.setObjectName("TitleBarSubtitle")
        
        logo_layout.addWidget(cube_icon)
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
        self.notifications_btn = QPushButton("🔔")  # Bell icon
        self.notifications_btn.setObjectName("GlassButton")
        self.notifications_btn.setFixedSize(36, 36)
        
        self.settings_btn = QPushButton("⚙️")  # Gear icon
        self.settings_btn.setObjectName("GlassButton") 
        self.settings_btn.setFixedSize(36, 36)
        
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
        
        layout.addWidget(self.notifications_btn)
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