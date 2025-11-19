# Scripts Directory (DEPRECATED)

**Note:** All scripts in this directory (`scripts/`) and `scripts_backup/` are **DEPRECATED** as of Phase 1 of the Merged Development Plan.

VirtFlow no longer uses external scripts or libvirt hooks for driver management. This entire directory and `scripts_backup/` should be deleted.

**REASON:**
All driver binding/unbinding logic (e.g., from `setup_gpu_passthrough.sh`, `gpu_worker.py`) has been consolidated directly into `src/backend/vfio_manager.py`.
All setup logic (e.g., from `setup_sudo_permissions.sh`, `install_libvirt_hooks.sh`) has been replaced by guided dialogs in the main UI, handled by `src/ui/main_window.py`.