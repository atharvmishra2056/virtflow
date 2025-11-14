#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""

def test_imports():
    try:
        # Test PySide6 imports
        from PySide6.QtWidgets import QApplication, QWidget
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon, QPixmap
        print("✓ PySide6 imports successful")
        
        # Test project imports
        import sys
        import os
        sys.path.append('src')
        
        import config
        print("✓ Config import successful")
        
        from models.vm_model import VMModel
        print("✓ VMModel import successful")
        
        from backend.vm_controller import VMState
        print("✓ VMController import successful")
        
        from utils.logger import logger
        print("✓ Logger import successful")
        
        # Test UI imports
        from ui.title_bar import TitleBarWidget
        print("✓ TitleBarWidget import successful")
        
        from ui.sidebar_widget import SidebarWidget
        print("✓ SidebarWidget import successful")
        
        from ui.main_stage_widget import MainStageWidget
        print("✓ MainStageWidget import successful")
        
        from ui.widgets.vm_list_item_widget import VMListItemWidget
        print("✓ VMListItemWidget import successful")
        
        from ui.main_window import MainWindow
        print("✓ MainWindow import successful")
        
        print("\n🎉 All imports successful! The application should work once PySide6 is installed.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_imports()
