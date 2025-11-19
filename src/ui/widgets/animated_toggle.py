"""
Animated Toggle Switch
Modern macOS/Android style toggle with smooth sliding animation
"""

from PySide6.QtCore import Qt, QSize, QRectF, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

class AnimatedToggle(QWidget):
    """
    Modern animated toggle switch with smooth sliding animation
    Similar to macOS/iOS and Android toggle switches
    """
    
    # Signal emitted when toggle state changes
    checkedChanged = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set fixed size
        self.setFixedSize(QSize(48, 28))
        
        # Toggle state
        self._checked = False
        
        # Set cursor
        self.setCursor(Qt.PointingHandCursor)
        
        # Colors
        self._track_color_off = QColor(255, 255, 255, 51)   # rgba(255, 255, 255, 0.2)
        self._track_color_on = QColor("#3b82f6")             # Blue
        self._thumb_color = QColor("#FFFFFF")               # White
        
        # Animation properties
        self._thumb_position = 0.0  # 0.0 = off, 1.0 = on
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animateStep)
        self._animation_duration = 200  # ms
        self._animation_steps = 20
        self._animation_step = 0
        self._animation_start = 0.0
        self._animation_end = 0.0
        
        # Update initial appearance
        self.update()
    
    def isChecked(self) -> bool:
        """Get current toggle state"""
        return self._checked
    
    def setChecked(self, checked: bool):
        """Set toggle state"""
        if self._checked != checked:
            self._checked = checked
            self._startAnimation()
            self.checkedChanged.emit(checked)
    
    def toggle(self):
        """Toggle the current state"""
        self.setChecked(not self._checked)
    
    def _startAnimation(self):
        """Start the sliding animation"""
        target_position = 1.0 if self._checked else 0.0
        
        # Start animation
        self._animation_start = self._thumb_position
        self._animation_end = target_position
        self._animation_step = 0
        
        # Calculate animation step interval
        interval = self._animation_duration // self._animation_steps
        self._animation_timer.start(interval)
    
    def mousePressEvent(self, event):
        """Handle mouse press to toggle state"""
        if event.button() == Qt.LeftButton:
            self.toggle()
        super().mousePressEvent(event)
    
    def _animateStep(self):
        """Perform one step of the animation"""
        self._animation_step += 1
        
        if self._animation_step >= self._animation_steps:
            # Animation complete
            self._thumb_position = self._animation_end
            self._animation_timer.stop()
        else:
            # Calculate eased position
            t = self._animation_step / self._animation_steps
            # Use cubic ease-in-out
            if t < 0.5:
                eased_t = 4 * t * t * t
            else:
                eased_t = 1 - pow(-2 * t + 2, 3) / 2
            
            self._thumb_position = self._animation_start + (self._animation_end - self._animation_start) * eased_t
        
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event for modern toggle appearance"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate dimensions
        width = self.width()
        height = self.height()
        track_height = 22
        track_width = 42
        thumb_diameter = 18
        
        # Center the track
        track_rect = QRectF(
            (width - track_width) / 2,
            (height - track_height) / 2,
            track_width,
            track_height
        )
        
        # Calculate thumb position
        thumb_x = track_rect.left() + 3 + self._thumb_position * (track_width - thumb_diameter - 6)
        thumb_y = (height - thumb_diameter) / 2
        thumb_rect = QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter)
        
        # Draw track (background)
        # Interpolate color based on current position
        r = self._track_color_off.red() + (self._track_color_on.red() - self._track_color_off.red()) * self._thumb_position
        g = self._track_color_off.green() + (self._track_color_on.green() - self._track_color_off.green()) * self._thumb_position
        b = self._track_color_off.blue() + (self._track_color_on.blue() - self._track_color_off.blue()) * self._thumb_position
        a = self._track_color_off.alpha() + (self._track_color_on.alpha() - self._track_color_off.alpha()) * self._thumb_position
        track_color = QColor(r, g, b, a)
        
        painter.setBrush(track_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(track_rect, track_height / 2, track_height / 2)
        
        # Draw thumb (circle)
        painter.setBrush(self._thumb_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(thumb_rect)
        
        # Add subtle shadow to thumb
        shadow_color = QColor(0, 0, 0, 30)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(shadow_color, 1))
        painter.drawEllipse(thumb_rect.adjusted(0, 0, 0, 0))
    
    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()
    
    def minimumSizeHint(self) -> QSize:
        return QSize(48, 28)
