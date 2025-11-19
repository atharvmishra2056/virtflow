#!/usr/bin/env python3
"""
DEPRECATED: This module's logic has been merged into backend.vfio_manager.py
as of Phase 1 of the development plan.

This file is no longer used by the application and should be deleted.

REASON: The logic for removing/loading NVIDIA drivers and binding/unbinding
devices is now centralized in the VFIOManager class, removing the need
for this separate subprocess script.
"""

import sys

def main():
    print("ERROR: gpu_worker.py is deprecated. Logic is now in backend.vfio_manager.py", file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':
    main()