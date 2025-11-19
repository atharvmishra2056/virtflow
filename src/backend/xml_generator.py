"""
libvirt XML Generator for Windows VMs with GPU Passthrough
PRODUCTION-READY - Fixed for Ubuntu 25.10 OVMF paths

PHASE 0 REFACTOR: This module is now the single source of truth for all
VM XML generation, merging logic from the deprecated vm_gpu_configurator.py.

PHASE 2.C REFACTOR: Added support for settings from HyperGlass dialog
(VRAM, 3D Accel, TPM).
"""

import uuid
import subprocess
from typing import List, Dict, Optional
from pathlib import Path
from shutil import copy2

from backend.gpu_detector import GPU
from utils.logger import logger
import config


class XMLGenerator:
    """Generate libvirt domain XML for Windows VMs"""
    
    def __init__(self):
        self.ovmf_code_path = self._find_ovmf_code_path()
        if not self.ovmf_code_path:
            logger.error("Could not find any OVMF_CODE.fd file. VM creation will fail.")
            raise FileNotFoundError("OVMF_CODE.fd not found in any standard location.")

        self.ovmf_vars_path = self._find_ovmf_vars_path()
        if not self.ovmf_vars_path:
            logger.error("Could not find any OVMF_VARS.fd file. VM creation will fail.")
            raise FileNotFoundError("OVMF_VARS.fd not found in any standard location.")


    def _find_ovmf_code_path(self) -> Optional[str]:
        """Find OVMF CODE firmware path on system"""
        possible_paths = [
            "/usr/share/OVMF/OVMF_CODE.fd",
            "/usr/share/qemu/OVMF_CODE.fd",
            "/usr/share/ovmf/OVMF_CODE.fd"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                logger.info(f"Using OVMF CODE firmware: {path}")
                return path
        
        # Fallback - use libvirt to detect
        try:
            result = subprocess.run(
                ['virsh', 'domcapabilities', '--machine', 'q35'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(result.stdout)
                
                for loader in root.findall('.//loader/value'):
                    path_str = loader.text
                    if path_str and 'OVMF_CODE' in path_str and Path(path_str).exists():
                        logger.info(f"Auto-detected OVMF CODE: {path_str}")
                        return path_str
        except Exception as e:
            logger.debug(f"Failed to auto-detect OVMF CODE: {e}")
        
        logger.warning("OVMF CODE firmware not found; VM launch may fail.")
        return None

    def _find_ovmf_vars_path(self) -> Optional[str]:
        """Find OVMF VARS template firmware path on system"""
        possible_paths = [
            "/usr/share/OVMF/OVMF_VARS.fd",
            "/usr/share/qemu/OVMF_VARS.fd",
            "/usr/share/ovmf/OVMF_VARS.fd"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                logger.info(f"Using OVMF VARS template: {path}")
                return path
        
        logger.warning("OVMF VARS template firmware not found; VM launch may fail.")
        return None

    def _prepare_ovmf_vars_file(self, vm_name: str) -> str:
        """
        Prepare NVRAM vars file per VM by copying template if missing.

        Returns full path to NVRAM vars file for given VM.
        """
        if not self.ovmf_vars_path:
            logger.error("Cannot prepare OVMF VARS file: Template path is not set.")
            return "" # VM will fail to start, but this avoids a crash

        # Store per-VM NVRAM files in a standard libvirt location
        nvram_dir = Path("/var/lib/libvirt/qemu/nvram/")
        nvram_dir.mkdir(parents=True, exist_ok=True)
        
        vm_nvram_path = nvram_dir / f"{vm_name}_VARS.fd"
        
        if not vm_nvram_path.exists():
            try:
                logger.info(f"Copying OVMF template to {vm_nvram_path}")
                copy2(self.ovmf_vars_path, vm_nvram_path)
                # TODO: Set correct permissions (chown libvirt-qemu)
            except Exception as e:
                logger.error(f"Failed to copy OVMF VARS template: {e}")
                return "" # Return empty path if copy fails

        return str(vm_nvram_path)

    def _calculate_cpu_topology(self, vcpus: int) -> Dict[str, int]:
        """Calculate CPU topology (sockets, cores, threads)"""
        # Simple topology: 1 socket, vcpus/2 cores, 2 threads
        if vcpus % 2 == 0 and vcpus >= 2:
            cores = vcpus // 2
            threads = 2
        else:
            cores = vcpus
            threads = 1
            
        return {
            "sockets": 1,
            "cores": cores,
            "threads": threads
        }

    def _generate_os_config(self, vm_name: str, nvram_path: str) -> str:
        """Generate OS boot and firmware configuration"""
        return f"""
            <os>
              <type arch='x86_64' machine='pc-q35-5.2'>hvm</type>
              <loader readonly='yes' type='pflash'>{self.ovmf_code_path}</loader>
              <nvram>{nvram_path}</nvram>
              <boot dev='hd'/>
              <boot dev='cdrom'/>
              <bootmenu enable='yes'/>
            </os>
        """

    def _generate_features(self) -> str:
        """Generate CPU and Hyper-V features"""
        return """
            <features>
              <acpi/>
              <apic/>
              <hyperv>
                <relaxed state='on'/>
                <vapic state='on'/>
                <spinlocks state='on' retries='8191'/>
                <vpindex state='on'/>
                <runtime state='on'/>
                <synic state='on'/>
                <stimer state='on'/>
                <reset state='on'/>
                <vendor_id state='on' value='1234567890ab'/>
                <frequencies state='on'/>
              </hyperv>
              <kvm>
                <hidden state='on'/>
              </kvm>
              <vmport state='off'/>
              <ioapic driver='kvm'/>
            </features>
        """

    def _generate_cpu_config(self, topology: Dict[str, int]) -> str:
        """Generate CPU configuration (host-passthrough)"""
        return f"""
            <cpu mode='host-passthrough' check='partial'>
              <topology sockets='{topology["sockets"]}' cores='{topology["cores"]}' threads='{topology["threads"]}'/>
            </cpu>
        """

    def _generate_clock_config(self) -> str:
        """Generate clock and timer configuration"""
        return """
            <clock offset='localtime'>
              <timer name='rtc' tickpolicy='catchup'/>
              <timer name='pit' tickpolicy='delay'/>
              <timer name='hpet' present='no'/>
              <timer name='hypervclock' present='yes'/>
            </clock>
        """

    def _generate_power_management(self) -> str:
        """Generate power management configuration"""
        return """
            <on_poweroff>destroy</on_poweroff>
            <on_reboot>restart</on_reboot>
            <on_crash>destroy</on_crash>
        """

    def _generate_devices_header(self) -> str:
        """Generate devices block header"""
        return """
            <devices>
              <emulator>/usr/bin/qemu-system-x86_64</emulator>
              <controller type='sata' index='0'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x1f' function='0x2'/>
              </controller>
              <controller type='pci' index='0' model='pcie-root'/>
              <controller type='pci' index='1' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0'/>
              </controller>
              <controller type='pci' index='2' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
              </controller>
              <controller type='pci' index='3' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
              </controller>
              <controller type='pci' index='4' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
              </controller>
              <controller type='pci' index='5' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x06' function='0x0'/>
              </controller>
              <controller type='pci' index='6' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
              </controller>
              <controller type='pci' index='7' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x08' function='0x0'/>
              </controller>
              <controller type='pci' index='8' model='pcie-root-port'>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x09' function='0x0'/>
              </controller>
              <controller type='virtio-serial' index='0'>
                <address type='pci' domain='0x0000' bus='0x02' slot='0x00' function='0x0'/>
              </controller>
        """

    def _generate_disk_config(self, disk_path: str) -> str:
        """Generate main disk configuration (vda)"""
        return f"""
              <disk type='file' device='disk'>
                <driver name='qemu' type='qcow2' cache='writeback' discard='unmap'/>
                <source file='{disk_path}'/>
                <target dev='vda' bus='virtio'/>
                <boot order='1'/>
                <address type='pci' domain='0x0000' bus='0x03' slot='0x00' function='0x0'/>
              </disk>
        """

    def _generate_cdrom_config(self, iso_path: str, virtio_iso_path: str) -> str:
        """Generate CD-ROM drives (Windows ISO and VirtIO ISO)"""
        return f"""
              <disk type='file' device='cdrom'>
                <driver name='qemu' type='raw'/>
                <source file='{iso_path}'/>
                <target dev='sda' bus='sata'/>
                <readonly/>
                <boot order='2'/>
                <address type='drive' controller='0' bus='0' target='0' unit='0'/>
              </disk>
              <disk type='file' device='cdrom'>
                <driver name='qemu' type='raw'/>
                <source file='{virtio_iso_path}'/>
                <target dev='sdb' bus='sata'/>
                <readonly/>
                <address type='drive' controller='0' bus='0' target='0' unit='1'/>
              </disk>
        """

    def _generate_network_config(self) -> str:
        """Generate VirtIO network configuration"""
        return """
              <interface type='network'>
                <mac address='52:54:00:00:00:01'/>
                <source network='default'/>
                <model type='virtio'/>
                <address type='pci' domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
              </interface>
        """

    # --- PHASE 0 REFACTOR (Task 0.3) ---
    # --- PHASE 2.C MOD: Added vram_mb ---
    def _generate_qxl_graphics(self, is_primary: bool = True, vram_mb: int = 64) -> str:
        """
        Generate SPICE/QXL graphics.
        This is ALWAYS included for SPICE input, but only 'primary' if
        GPU passthrough is not enabled.
        """
        primary_attr = " primary='yes'" if is_primary else ""
        vram_kb = vram_mb * 1024 # Convert MB to KB for libvirt
        
        return f"""
              <graphics type='spice' autoport='yes'>
                <listen type='address'/>
                <image compression='off'/>
              </graphics>
              <audio id='1' type='spice'/>
              <video>
                <model type='qxl' ram='{vram_kb}' vram='{vram_kb}' vgamem='16384' heads='1'{primary_attr}/>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x0'/>
              </video>
        """
    # --- END REFACTOR ---

    # --- PHASE 0 REFACTOR (Task 0.1) ---
    def _generate_pci_hostdev(self, pci_address: str, bus_slot: int) -> str:
        """
        Generate PCI hostdev XML for GPU passthrough.
        Includes guest PCI address assignment logic merged from vm_gpu_configurator.
        """
        try:
            # Parse 0000:01:00.0 format
            domain, bus, slot_func = pci_address.split(':')
            slot, func = slot_func.split('.')
            
            domain_s = f"{int(domain, 16):04x}"
            bus_s = f"{int(bus, 16):02x}"
            slot_s = f"{int(slot, 16):02x}"
            func_s = f"{int(func, 16):x}"

            # Assign guest PCI address on a dedicated bus (e.g., bus 0x06)
            # Use bus_slot to give each device a unique slot (0, 1, 2, etc.)
            guest_bus = "0x06" 
            guest_slot = f"0x{bus_slot:02x}"

            return f"""
              <hostdev mode='subsystem' type='pci' managed='yes'>
                <source>
                  <address domain='0x{domain_s}' bus='0x{bus_s}' slot='0x{slot_s}' function='0x{func_s}'/>
                </source>
                <address type='pci' domain='0x0000' bus='{guest_bus}' slot='{guest_slot}' function='0x0'/>
              </hostdev>
            """
        except Exception as e:
            logger.error(f"Failed to parse PCI address '{pci_address}': {e}")
            return ""
    # --- END REFACTOR ---

    # --- PHASE 0 REFACTOR (Task 0.2) ---
    def _generate_looking_glass_shmem(self) -> str:
        """
        Generates the IVSHMEM device required for Looking Glass.
        """
        return """
              <shmem name='looking-glass'>
                <model type='ivshmem-plain'/>
                <size unit='M'>64</size>
                <address type='pci' domain='0x0000' bus='0x04' slot='0x01' function='0x0'/>
              </shmem>
        """
    # --- END REFACTOR ---

    # --- PHASE 2.C REFACTOR: New method for 3D Accel ---
    def _generate_virtio_gpu(self, vram_mb: int = 64, accel_3d: bool = False) -> str:
        """
        Generates a VirtIO-VGA adapter, optionally with 3D acceleration.
        This is separate from the QXL/SPICE device.
        """
        vram_kb = vram_mb * 1024
        accel_str = "<acceleration accel3d='yes'/>" if accel_3d else ""
        
        return f"""
              <video>
                <model type='virtio' vram='{vram_kb}' heads='1'>
                  {accel_str}
                </model>
                <address type='pci' domain='0x0000' bus='0x09' slot='0x00' function='0x0'/>
              </video>
        """
    # --- END PHASE 2.C ---

    def _generate_console(self) -> str:
        """Generate console, serial, and QEMU agent channels"""
        return """
              <serial type='pty'>
                <target type='isa-serial' port='0'>
                  <model name='isa-serial'/>
                </target>
              </serial>
              <console type='pty'>
                <target type='serial' port='0'/>
              </console>
              <channel type='spicevmc'>
                <target type='virtio' name='com.redhat.spice.0'/>
                <address type='virtio-serial' controller='0' bus='0' port='1'/>
              </channel>
              <channel type='unix'>
                <target type='virtio' name='org.qemu.guest_agent.0'/>
                <address type='virtio-serial' controller='0' bus='0' port='2'/>
              </channel>
        """

    def _generate_input_devices(self) -> str:
        """Generate input devices (tablet for SPICE)"""
        return """
              <input type='tablet' bus='usb'>
                <address type='usb' bus='0' port='1'/>
              </input>
              <input type='mouse' bus='ps2'/>
              <input type='keyboard' bus='ps2'/>
        """

    def _generate_tpm_device(self) -> str:
        """Generate TPM device (for Windows 11)"""
        return """
              <tpm model='tpm-tis'>
                <backend type='passthrough'>
                  <device path='/dev/tpm0'/>
                </backend>
                <address type='pci' domain='0x0000' bus='0x05' slot='0x00' function='0x0'/>
              </tpm>
        """

    def _generate_other_devices(self) -> str:
        """Generate other VirtIO devices (balloon, rng)"""
        return """
              <memballoon model='virtio'>
                <address type='pci' domain='0x0000' bus='0x07' slot='0x00' function='0x0'/>
              </memballoon>
              <rng model='virtio'>
                <backend model='random'>/dev/urandom</backend>
                <address type='pci' domain='0x0000' bus='0x08' slot='0x00' function='0x0'/>
              </rng>
            </devices>
        """

    # --- PHASE 2.C MOD: Added settings dict ---
    def generate_windows_vm_xml(
        self,
        vm_name: str,
        vcpus: int,
        memory_mb: int,
        disk_path: str,
        iso_path: str,
        virtio_iso_path: str,
        enable_gpu_passthrough: bool = False,
        gpu: Optional[GPU] = None,
        enable_tpm: bool = True, # Retain for default
        display_preference: str = "spice",
        settings: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate the complete libvirt XML for a new Windows VM.
        """
        if settings is None:
            settings = {}
            
        if not self.ovmf_code_path or not self.ovmf_vars_path:
            raise FileNotFoundError("OVMF firmware (CODE or VARS) not found. Cannot generate VM.")

        vm_uuid = str(uuid.uuid4())
        topology = self._calculate_cpu_topology(vcpus)
        nvram_path = self._prepare_ovmf_vars_file(vm_name)
        if not nvram_path:
            raise RuntimeError(f"Failed to prepare NVRAM file for {vm_name}")
        
        xml_parts = [
            f"<domain type='kvm'>",
            f"  <name>{vm_name}</name>",
            f"  <uuid>{vm_uuid}</uuid>",
            f"  <memory unit='MiB'>{memory_mb}</memory>",
            f"  <currentMemory unit='MiB'>{memory_mb}</currentMemory>",
            f"  <vcpu placement='static'>{vcpus}</vcpu>",
            "    <cpu mode='host-passthrough' check='partial'>",
            f"      <topology sockets='{topology['sockets']}' cores='{topology['cores']}' threads='{topology['threads']}'/>",
            "    </cpu>",
            self._generate_os_config(vm_name, nvram_path),
            self._generate_features(),
            self._generate_clock_config(),
            self._generate_power_management(),
            self._generate_devices_header(),
            self._generate_disk_config(disk_path),
            self._generate_cdrom_config(iso_path, virtio_iso_path),
            self._generate_network_config(),
        ]

        # --- PHASE 0 REFACTOR (Task 0.3) ---
        # Always include SPICE/QXL.
        # SPICE is required for Looking Glass input or basic install.
        # It's only 'primary' if GPU passthrough is OFF.
        is_primary_display = not enable_gpu_passthrough
        # --- PHASE 2.C MOD: Read VRAM for QXL ---
        vram = int(settings.get("vram", "128"))
        xml_parts.append("    ")
        xml_parts.append(self._generate_qxl_graphics(is_primary=is_primary_display, vram_mb=vram))
        # --- END REFACTOR ---

        # --- PHASE 2.C MOD: Add VirtIO GPU if 3D Accel is on ---
        if settings.get("3d_accel", "false").lower() == "true":
            xml_parts.append("    ")
            xml_parts.append(self._generate_virtio_gpu(vram_mb=vram, accel_3d=True))
        # --- END MOD ---

        if enable_gpu_passthrough and gpu:
            xml_parts.append("    ")
            # --- PHASE 0 REFACTOR (Task 0.1) ---
            # Enumerate devices to assign unique guest PCI slots
            for i, device in enumerate(gpu.all_devices):
                xml_parts.append(self._generate_pci_hostdev(device.address, bus_slot=i))
            # --- END REFACTOR ---
        
        # --- PHASE 0 REFACTOR (Task 0.2) ---
        # Add Looking Glass IVSHMEM device if selected
        if display_preference == "looking-glass":
            xml_parts.append("    ")
            xml_parts.append(self._generate_looking_glass_shmem())
        # --- END REFACTOR ---

        xml_parts.extend([
            self._generate_console(),
            self._generate_input_devices(),
        ])

        # --- PHASE 2.C MOD: Check setting OR param for TPM ---
        tpm_enabled_setting = settings.get("tpm_enabled", "false").lower() == "true"
        if enable_tpm or tpm_enabled_setting:
            xml_parts.append(self._generate_tpm_device())
        # --- END MOD ---
            
        xml_parts.extend([
            self._generate_other_devices(),
            "</domain>"
        ])
        
        return "\n".join(xml_parts)