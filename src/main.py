#!/usr/bin/env python3
"""
VirtFlow - Main Entry Point
Modern GPU Passthrough Virtual Machine Manager
"""

import sys
import os
from pathlib import Path

# PySide6 imports
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QIcon

# Local imports
from ui.main_window import MainWindow
from utils.logger import setup_logger
from backend.system_checker import SystemChecker
import config


def check_system_requirements():
    """
    Check if system meets requirements for running VirtFlow
    Returns: tuple (bool, str) - (success, error_message)
    """
    from backend.dependency_checker import DependencyChecker
    
    checker_dep = DependencyChecker()
    checker = SystemChecker()
    
    # Check if running as root (bad)
    if os.geteuid() == 0:
        return False, "Please do not run VirtFlow as root. Add your user to 'libvirt' group instead."
    
    # Check system dependencies
    deps_ok, missing_packages = checker_dep.check_all_dependencies()
    if not deps_ok:
        install_cmd = checker_dep.get_install_command(missing_packages)
        return False, (
            f"Missing required packages:\n\n{', '.join(missing_packages)}\n\n"
            f"Install them with:\n{install_cmd}"
        )
    
    # Check user groups
    groups_ok, missing_groups = checker_dep.check_user_groups()
    if not groups_ok:
        return False, (
            f"User not in required groups: {', '.join(missing_groups)}\n\n"
            f"Add yourself to groups:\n"
            f"sudo usermod -aG {' '.join(missing_groups)} $USER\n\n"
            f"Then log out and log back in."
        )
    
    # Check libvirt daemon
    if not checker.is_libvirt_running():
        return False, "libvirtd service is not running. Please start it:\nsudo systemctl start libvirtd"
    
    # Check KVM support
    if not checker.has_kvm_support():
        return False, "KVM virtualization is not available. Check BIOS settings and CPU support."
    
    # Check IOMMU (warning only, not fatal)
    if not checker.has_iommu_enabled():
        print("[WARNING] IOMMU is not enabled. GPU passthrough will not work.")
        print("Please enable IOMMU in BIOS and add 'intel_iommu=on' or 'amd_iommu=on' to kernel parameters.")
    
    return True, ""


def main():
    """Main application entry point"""
    
    # Set application metadata
    QCoreApplication.setApplicationName(config.APP_NAME)
    QCoreApplication.setApplicationVersion(config.APP_VERSION)
    QCoreApplication.setOrganizationName(config.APP_AUTHOR)
    
    # Enable High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application instance
    app = QApplication(sys.argv)
    
    # Setup logging
    logger = setup_logger()
    logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
    
    # Check system requirements
    success, error_msg = check_system_requirements()
    if not success:
        from ui.setup_dialog import SetupDialog
        setup = SetupDialog()
        if setup.exec() != QDialog.Accepted:
            return 1
    
    # Set application icon
    icon_path = config.ICONS_DIR / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Create and show main window
    try:
        main_window = MainWindow()
        main_window.show()
        logger.info("Main window displayed successfully")
    except Exception as e:
        logger.exception("Failed to create main window")
        QMessageBox.critical(
            None,
            f"{config.APP_NAME} - Startup Error",
            f"Failed to initialize application:\n{str(e)}"
        )
        return 1
    
    # Run application event loop
    exit_code = app.exec()
    logger.info(f"{config.APP_NAME} exiting with code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
