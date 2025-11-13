"""
First-Run Setup Dialog - Guides user through initial setup
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt

from backend.dependency_checker import DependencyChecker
from utils.logger import logger


class SetupDialog(QDialog):
    """First-run setup dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("VirtFlow Setup")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self.checker = DependencyChecker()
        
        self._setup_ui()
        self._run_checks()
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        title = QLabel("VirtFlow System Setup")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        info = QLabel(
            "Checking system requirements...\n\n"
            "VirtFlow requires:\n"
            "• QEMU/KVM packages\n"
            "• libvirt daemon\n"
            "• User permissions (libvirt, kvm groups)\n"
            "• IOMMU support (for GPU passthrough)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        
        self.ok_btn = QPushButton("Continue")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        layout.addWidget(self.ok_btn)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QLabel, QTextEdit {
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #0D7377;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
        """)
    
    def _run_checks(self):
        """Run system checks"""
        results = []
        all_ok = True
        
        # Check dependencies
        self.progress.setValue(25)
        deps_ok, missing = self.checker.check_all_dependencies()
        
        if deps_ok:
            results.append("✓ All required packages installed")
        else:
            results.append(f"✗ Missing packages: {', '.join(missing)}")
            results.append(f"   Install: {self.checker.get_install_command(missing)}")
            all_ok = False
        
        # Check groups
        self.progress.setValue(50)
        groups_ok, missing_groups = self.checker.check_user_groups()
        
        if groups_ok:
            results.append("✓ User in required groups (libvirt, kvm)")
        else:
            results.append(f"✗ User not in groups: {', '.join(missing_groups)}")
            results.append(f"   Fix: sudo usermod -aG {' '.join(missing_groups)} $USER")
            results.append("   Then log out and log back in")
            all_ok = False
        
        # Check libvirt
        self.progress.setValue(75)
        if self.checker.check_libvirt_connection():
            results.append("✓ libvirt daemon accessible")
        else:
            results.append("✗ Cannot connect to libvirt")
            results.append("   Fix: sudo systemctl start libvirtd")
            all_ok = False
        
        self.progress.setValue(100)
        
        # Display results
        self.results_text.setPlainText('\n'.join(results))
        
        if all_ok:
            self.ok_btn.setEnabled(True)
            self.results_text.append("\n✓ System ready for VirtFlow!")
        else:
            self.results_text.append("\n✗ Please fix the issues above and restart VirtFlow")
