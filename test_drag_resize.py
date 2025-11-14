#!/usr/bin/env python3
"""
Test script to verify dragging and resizing works
"""
import sys
sys.path.append('src')

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drag & Resize Test")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(400, 300)
        
        # Store dragging state
        self.drag_start_position = None
        self.window_start_position = None
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        
        # Title bar
        title_bar = QLabel("Drag me to move window")
        title_bar.setStyleSheet("""
            QLabel {
                background: #2563eb;
                color: white;
                padding: 10px;
                font-weight: bold;
            }
        """)
        title_bar.setFixedHeight(40)
        
        # Content
        content = QLabel("Resize from bottom-right corner")
        content.setStyleSheet("""
            QLabel {
                background: #f1f5f9;
                color: #1e293b;
                padding: 20px;
            }
        """)
        
        layout.addWidget(title_bar)
        layout.addWidget(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Add resize grip
        from PySide6.QtWidgets import QSizeGrip
        self.resize_grip = QSizeGrip(self)
        self.resize_grip.setFixedSize(20, 20)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint()
            self.window_start_position = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if (event.buttons() == Qt.LeftButton and 
            self.drag_start_position is not None):
            
            delta = event.globalPosition().toPoint() - self.drag_start_position
            new_pos = self.window_start_position + delta
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = None
            self.window_start_position = None
            event.accept()
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'resize_grip'):
            self.resize_grip.move(self.width() - 20, self.height() - 20)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    print("✓ Test window created")
    print("✓ Try dragging the window by clicking and dragging")
    print("✓ Try resizing from the bottom-right corner")
    
    sys.exit(app.exec())
