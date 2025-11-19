"""
Icon Utility (Phase 2 Redux Fix)
Provides functions to recolor black SVG icons.
"""

# --- THESE IMPORTS ARE REQUIRED ---
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QSize
# --- END IMPORTS ---

def create_recolored_icon(icon_path: str, color: str | QColor) -> QIcon:
    """
    Loads a black SVG and repaints it with a single color.
    """
    if not isinstance(color, QColor):
        color = QColor(color)
        
    # 1. Load the black SVG as the mask
    mask_pixmap = QPixmap(icon_path)
    
    # 2. Create the new pixmap
    icon_pixmap = QPixmap(mask_pixmap.size())
    icon_pixmap.fill(Qt.transparent)
    
    # 3. Paint the new pixmap
    painter = QPainter(icon_pixmap)
    # Set high-quality rendering
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    
    painter.setCompositionMode(QPainter.CompositionMode_Source)
    painter.drawPixmap(0, 0, mask_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn) # Masking
    painter.fillRect(icon_pixmap.rect(), color)
    painter.end()
    
    return QIcon(icon_pixmap)

def create_stateful_icon(icon_path: str, color_off: str | QColor, color_on: str | QColor) -> QIcon:
    """
    Loads a black SVG and creates a state-aware QIcon
    with different colors for 'On' and 'Off' states.
    """
    if not isinstance(color_off, QColor):
        color_off = QColor(color_off)
    if not isinstance(color_on, QColor):
        color_on = QColor(color_on)

    # Use a standard size for consistency
    pixmap_size = QSize(32, 32)

    # 1. Create the 'Off' (e.g., white) icon
    icon_off = create_recolored_icon(icon_path, color_off).pixmap(pixmap_size)
    
    # 2. Create the 'On' (e.g., blue) icon
    icon_on = create_recolored_icon(icon_path, color_on).pixmap(pixmap_size)

    # 3. Create a state-aware QIcon
    stateful_icon = QIcon()
    stateful_icon.addPixmap(icon_off, QIcon.Mode.Normal, QIcon.State.Off)
    stateful_icon.addPixmap(icon_on, QIcon.Mode.Normal, QIcon.State.On)
    
    # Add states for when the button is active/pressed (e.g. sidebar)
    stateful_icon.addPixmap(icon_on, QIcon.Mode.Active, QIcon.State.Off)
    stateful_icon.addPixmap(icon_on, QIcon.Mode.Active, QIcon.State.On)

    return stateful_icon