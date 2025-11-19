"""
HyperGlass Custom Widgets (Phase 2 Redux)
Provides reusable Qt components styled by hyperglass.qss
"""

from PySide6.QtWidgets import (
    QLineEdit, QCheckBox, QSlider, QComboBox, QPushButton, QFrame,
    QLabel, QHBoxLayout, QWidget, QVBoxLayout
)
from PySide6.QtCore import Qt, QSize
# --- FIX: Add QColor ---
from PySide6.QtGui import QIcon, QColor
import config
# --- FIX: Import recolor util ---
from .icon_utils import create_recolored_icon, create_stateful_icon
from .animated_toggle import AnimatedToggle

class GlassInput(QLineEdit):
    """ .glass-input """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("class", "GlassInput")

# --- FIX: Point 4 - New GlassToggle ---
class GlassToggle(AnimatedToggle):
    """ .toggle-checkbox (modern animated style) """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("class", "GlassToggle")
# --- END FIX ---

class GlassSlider(QSlider):
    """ input[type=range] """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("class", "GlassSlider")
        self.setOrientation(Qt.Horizontal)

# --- FIX: Point 3 - Re-implement GlassSelect to fix icon ---
class GlassSelect(QFrame):
    """ .glass-input (select) - Rebuilt as a custom widget """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set class to get .GlassInput style (border, bg, radius)
        self.setProperty("class", "GlassInput")
        self.setMinimumHeight(42) # Match GlassInput padding
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0) # Less right margin for arrow
        layout.setSpacing(8)
        
        self.combo_box = QComboBox()
        # Make the combobox transparent, borderless
        self.combo_box.setStyleSheet("""
            QComboBox {
                background: transparent; 
                border: none; 
                color: white;
                font-size: 14px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; } /* Hide default arrow */
            QComboBox QAbstractItemView {
                background: #1a1a1e;
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: white;
                selection-background-color: #3b82f6;
                padding: 4px;
            }
        """)
        self.combo_box.setFrame(False)
        
        # Create and set the white dropdown arrow
        arrow_icon = create_recolored_icon(
            str(config.ICONS_DIR / "caret-down.svg"),
            QColor(255, 255, 255, 150) # White 60%
        )
        self.arrow_label = QLabel()
        self.arrow_label.setPixmap(arrow_icon.pixmap(QSize(12, 12)))
        
        layout.addWidget(self.combo_box, 1) # Add with stretch
        layout.addWidget(self.arrow_label)
        
        # --- Expose QComboBox API ---
        self.addItems = self.combo_box.addItems
        self.currentText = self.combo_box.currentText
        self.setCurrentText = self.combo_box.setCurrentText
        self.currentIndexChanged = self.combo_box.currentIndexChanged
        self.findText = self.combo_box.findText
        self.setCurrentIndex = self.combo_box.setCurrentIndex
        
    def currentText(self) -> str:
        return self.combo_box.currentText()
        
    def addItems(self, items: list[str]):
        self.combo_box.addItems(items)
# --- END FIX ---

class GlassCard(QFrame):
    """ .glass-card """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("class", "GlassCard")

class SidebarButton(QPushButton):
    """ .nav-item (using recolored icons) """
    def __init__(self, icon: str, text: str, *args, **kwargs):
        super().__init__(f"  {text}", *args, **kwargs)
        self.setProperty("class", "SidebarButton")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        
        icon_path = str(config.ICONS_DIR / icon)
        color_off = QColor(255, 255, 255, 204) # White 80%
        color_on = QColor("#60a5fa")          # Active Blue
        
        stateful_icon = create_stateful_icon(icon_path, color_off, color_on)
        
        self.setIcon(stateful_icon)
        self.setIconSize(QSize(20, 20))
        # The QSS :checked selector will handle the text color

class PanelHeader(QWidget):
    """ Title/Subtitle for a settings panel """
    def __init__(self, title: str, subtitle: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setProperty("class", "PanelTitle")
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("class", "PanelSubtitle")
        
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
