"""
Animated Background Widget (Nebula UI)
Creates a 3D-like animated background similar to the Three.js effect in GG.html
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, QRect, Qt
from PySide6.QtGui import QPainter, QBrush, QRadialGradient, QColor, QPen
import math
import random

class FloatingOrb:
    """Represents a floating orb in the background"""
    def __init__(self, x, y, size, color, vel_x=0, vel_y=0):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.vel_x = vel_x
        self.vel_y = vel_y
        self.rotation = 0
        self.pulse_phase = random.uniform(0, math.pi * 2)
        
    def update(self, width, height, time):
        """Update orb position and properties"""
        # Move the orb
        self.x += self.vel_x
        self.y += self.vel_y
        
        # Bounce off edges
        if self.x <= 0 or self.x >= width:
            self.vel_x *= -1
        if self.y <= 0 or self.y >= height:
            self.vel_y *= -1
            
        # Keep in bounds
        self.x = max(0, min(width, self.x))
        self.y = max(0, min(height, self.y))
        
        # Update rotation and pulse
        self.rotation += 0.01
        self.pulse_phase += 0.02

class AnimatedBackground(QWidget):
    """Animated background widget with floating orbs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnimatedBackground")
        
        # Create floating orbs
        self.orbs = []
        self.time = 0
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)  # ~60 FPS
        
        # Initialize orbs
        self.init_orbs()
        
    def init_orbs(self):
        """Initialize floating orbs"""
        colors = [
            QColor(79, 70, 229, 100),   # Indigo
            QColor(192, 38, 211, 100),  # Fuchsia  
            QColor(6, 182, 212, 100),   # Cyan
            QColor(99, 102, 241, 100),  # Blue
            QColor(168, 85, 247, 100),  # Purple
        ]
        
        for i in range(8):  # Create 8 orbs
            x = random.uniform(0, 800)
            y = random.uniform(0, 600)
            size = random.uniform(80, 200)
            color = random.choice(colors)
            vel_x = random.uniform(-0.5, 0.5)
            vel_y = random.uniform(-0.5, 0.5)
            
            orb = FloatingOrb(x, y, size, color, vel_x, vel_y)
            self.orbs.append(orb)
    
    def update_animation(self):
        """Update animation frame"""
        self.time += 0.016  # 16ms per frame
        
        # Update all orbs
        for orb in self.orbs:
            orb.update(self.width(), self.height(), self.time)
            
        self.update()  # Trigger repaint
    
    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        # Reinitialize orbs for new size
        if self.width() > 0 and self.height() > 0:
            self.init_orbs()
    
    def paintEvent(self, event):
        """Paint the animated background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill with dark background
        painter.fillRect(self.rect(), QColor(15, 23, 42))  # #0f172a
        
        # Draw orbs with blur effect
        for orb in self.orbs:
            # Calculate pulse effect
            pulse = 0.8 + 0.2 * math.sin(orb.pulse_phase)
            current_size = orb.size * pulse
            
            # Create radial gradient for glow effect
            gradient = QRadialGradient(orb.x, orb.y, current_size / 2)
            
            # Center color (more opaque)
            center_color = QColor(orb.color)
            center_color.setAlpha(int(orb.color.alpha() * 0.8))
            gradient.setColorAt(0, center_color)
            
            # Mid color
            mid_color = QColor(orb.color)
            mid_color.setAlpha(int(orb.color.alpha() * 0.4))
            gradient.setColorAt(0.7, mid_color)
            
            # Edge color (transparent)
            edge_color = QColor(orb.color)
            edge_color.setAlpha(0)
            gradient.setColorAt(1, edge_color)
            
            # Draw the orb
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            
            orb_rect = QRect(
                int(orb.x - current_size / 2),
                int(orb.y - current_size / 2),
                int(current_size),
                int(current_size)
            )
            
            painter.drawEllipse(orb_rect)
        
        # Add subtle camera sway effect
        sway_x = 2 * math.sin(self.time * 0.5)
        sway_y = 2 * math.cos(self.time * 0.5)
        
        # Apply transform for sway (subtle movement)
        painter.translate(sway_x, sway_y)
        
        painter.end()
