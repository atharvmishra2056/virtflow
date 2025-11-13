#!/usr/bin/env python3
"""
VirtFlow - Modern GPU Passthrough Virtual Machine Manager
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

setup(
    name="virtflow",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Modern GPU Passthrough VM Manager for KVM/QEMU",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/virtflow",
    license="GPL-3.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "ui": ["styles/*.qss", "assets/**/*"],
    },
    include_package_data=True,
    install_requires=[
        "PySide6>=6.5.0",
        "libvirt-python>=9.0.0",
        "psutil>=5.9.0",
        "pyqtdarktheme>=2.1.0",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "virtflow=main:main",
        ],
        "gui_scripts": [
            "virtflow-gui=main:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Virtualization",
        "Topic :: Desktop Environment",
    ],
    keywords="virtualization kvm qemu gpu-passthrough vfio libvirt vm",
)
