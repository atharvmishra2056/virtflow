"""
libvirt XML Generator for Windows VMs with GPU Passthrough
PRODUCTION-READY - Fixed for Ubuntu 25.10 OVMF paths
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


    def _find_ovmf_code_path(self) -> str:
        """Find OVMF CODE firmware path on system"""
        possible_paths = [
            "/usr/share/OVMF/OVMF_CODE_4M.ms.fd",
            "/usr/share/OVMF/OVMF_CODE_4M.fd",
            "/usr/share/OVMF/OVMF_CODE.fd",
            "/usr/share/edk2-ovmf/OVMF_CODE.fd",
            "/usr/share/qemu/OVMF_CODE.fd"
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
                    path = loader.text
                    if path and 'OVMF_CODE' in path and Path(path).exists():
                        logger.info(f"Auto-detected OVMF CODE: {path}")
                        return path
        except Exception as e:
            logger.debug(f"Failed to auto-detect OVMF: {e}")
        
        # Default fallback
        logger.warning("OVMF CODE firmware not found; VM launch may fail.")
        return "/usr/share/OVMF/OVMF_CODE_4M.fd"

    def _prepare_ovmf_vars_file(self, vm_name: str) -> str:
        """
        Prepare NVRAM vars file per VM by copying template if missing.

        Returns full path to NVRAM vars file for given VM.
        """
        nvram_dir = Path.home() / ".local" / "share" / "virtflow" / "nvram"
        nvram_dir.mkdir(parents=True, exist_ok=True)
        nvram_path = nvram_dir / f"{vm_name}_VARS.fd"

        templates = [
            Path("/usr/share/OVMF/OVMF_VARS_4M.ms.fd"),
            Path("/usr/share/OVMF/OVMF_VARS_4M.fd"),
            Path("/usr/share/OVMF/OVMF_VARS.fd"),
        ]

        for template_path in templates:
            if template_path.exists():
                if not nvram_path.exists():
                    copy2(str(template_path), str(nvram_path))
                    logger.info(f"Copied OVMF vars template for VM '{vm_name}'")
                return str(nvram_path)

        logger.warning("OVMF vars template not found; boot may fail.")
        return str(nvram_path)
    
    def generate_windows_vm_xml(
        self,
        vm_name: str,
        memory_mb: int,
        vcpus: int,
        disk_path: str,
        iso_path: str,
        virtio_iso_path: str,
        gpu: Optional[GPU] = None,
        enable_tpm: bool = True,
        enable_gpu_passthrough: bool = False
    ) -> str:
        """
        Generate complete XML for Windows 10/11 VM
        """
        # Check if OVMF exists
        if not Path(self.ovmf_code_path).exists():
            raise FileNotFoundError(
                f"OVMF firmware not found at {self.ovmf_code_path}\n\n"
                "Install OVMF with: sudo apt install ovmf"
            )
        
        vm_uuid = str(uuid.uuid4())
        cpu_topology = self._calculate_cpu_topology(vcpus)
        
        # Build XML
        xml_parts = []
        
        # Domain header
        xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_parts.append('<domain type="kvm">')
        xml_parts.append(f'  <name>{vm_name}</name>')
        xml_parts.append(f'  <uuid>{vm_uuid}</uuid>')
        xml_parts.append(f'  <metadata>')
        xml_parts.append(f'    <libosinfo:libosinfo xmlns:libosinfo="http://libosinfo.org/xmlns/libvirt/domain/1.0">')
        xml_parts.append(f'      <libosinfo:os id="http://microsoft.com/win/11"/>')
        xml_parts.append(f'    </libosinfo:libosinfo>')
        xml_parts.append(f'  </metadata>')
        
        # Memory
        xml_parts.append(f'  <memory unit="KiB">{memory_mb * 1024}</memory>')
        xml_parts.append(f'  <currentMemory unit="KiB">{memory_mb * 1024}</currentMemory>')
        
        # vCPUs
        xml_parts.append(f'  <vcpu placement="static">{vcpus}</vcpu>')
        
        # OS boot configuration
        xml_parts.append(self._generate_os_config(vm_name, enable_tpm))
        
        # Features
        xml_parts.append(self._generate_features())
        
        # CPU configuration
        xml_parts.append(self._generate_cpu_config(vcpus, cpu_topology))
        
        # Clock
        xml_parts.append(self._generate_clock_config())
        
        # Power management
        xml_parts.append('  <on_poweroff>destroy</on_poweroff>')
        xml_parts.append('  <on_reboot>restart</on_reboot>')
        xml_parts.append('  <on_crash>destroy</on_crash>')
        
        # Devices
        xml_parts.append('  <devices>')
        xml_parts.append('    <emulator>/usr/bin/qemu-system-x86_64</emulator>')
        
        # Storage controllers first
        xml_parts.append('    <controller type="sata" index="0">')
        xml_parts.append('      <address type="pci" domain="0x0000" bus="0x00" slot="0x1f" function="0x2"/>')
        xml_parts.append('    </controller>')
        
        # Disk (main Windows installation)
        xml_parts.append(self._generate_disk_config(disk_path))
        
        # CD-ROM drives (Windows ISO + VirtIO ISO)
        xml_parts.append(self._generate_cdrom_config(iso_path, 'sda'))
        xml_parts.append(self._generate_cdrom_config(virtio_iso_path, 'sdb'))
        
        # Network
        xml_parts.append(self._generate_network_config())
        
        # Graphics and input
        if enable_gpu_passthrough and gpu:
            # GPU passthrough mode - add all GPU devices
            logger.info(f"Adding GPU passthrough for {gpu.full_name}")
            for device in gpu.all_devices:
                xml_parts.append(self._generate_pci_hostdev(device.address))
        else:
            # Basic graphics mode (QXL/SPICE)
            xml_parts.append(self._generate_qxl_graphics())
        
        # Console and serial
        xml_parts.append(self._generate_console())
        
        # USB and input devices
        xml_parts.append(self._generate_input_devices())
        
        # TPM for Windows 11
        if enable_tpm:
            xml_parts.append(self._generate_tpm_device())
        
        # Memory balloon
        xml_parts.append('    <memballoon model="virtio">')
        xml_parts.append('      <address type="pci" domain="0x0000" bus="0x05" slot="0x00" function="0x0"/>')
        xml_parts.append('    </memballoon>')
        
        # RNG device
        xml_parts.append('    <rng model="virtio">')
        xml_parts.append('      <backend model="random">/dev/urandom</backend>')
        xml_parts.append('      <address type="pci" domain="0x0000" bus="0x06" slot="0x00" function="0x0"/>')
        xml_parts.append('    </rng>')
        
        # Close devices and domain
        xml_parts.append('  </devices>')
        xml_parts.append('</domain>')
        
        return '\n'.join(xml_parts)
    
    def _calculate_cpu_topology(self, vcpus: int) -> Dict[str, int]:
        """Calculate optimal CPU topology"""
        return {
            'sockets': 1,
            'cores': vcpus,
            'threads': 1
        }
    
    def _generate_os_config(self, vm_name: str, enable_tpm: bool) -> str:
        nvram_path = self._prepare_ovmf_vars_file(vm_name)
        config = [
            '  <os>',
            '    <type arch="x86_64" machine="q35">hvm</type>',
            f'    <loader readonly="yes" type="pflash">{self.ovmf_code_path}</loader>',
            f'    <nvram>{nvram_path}</nvram>',
            '    <boot dev="cdrom"/>',
            '    <boot dev="hd"/>',
            '    <bootmenu enable="yes"/>',
            '  </os>'
        ]
        return '\n'.join(config)
    
    def _generate_features(self) -> str:
        """Generate features with Hyper-V enlightenments"""
        config = [
            '  <features>',
            '    <acpi/>',
            '    <apic/>',
            '    <hyperv mode="custom">',
            '      <relaxed state="on"/>',
            '      <vapic state="on"/>',
            '      <spinlocks state="on" retries="8191"/>',
            '      <vpindex state="on"/>',
            '      <runtime state="on"/>',
            '      <synic state="on"/>',
            '      <stimer state="on"/>',
            '      <reset state="on"/>',
            '      <vendor_id state="on" value="kvm hyperv"/>',
            '      <frequencies state="on"/>',
            '    </hyperv>',
            '    <kvm>',
            '      <hidden state="on"/>',  # NVIDIA Error 43 fix
            '    </kvm>',
            '    <vmport state="off"/>',
            '    <ioapic driver="kvm"/>',
            '  </features>'
        ]
        return '\n'.join(config)
    
    def _generate_cpu_config(self, vcpus: int, topology: Dict) -> str:
        """Generate CPU configuration"""
        config = [
            '  <cpu mode="host-passthrough" check="none" migratable="on">',
            f'    <topology sockets="{topology["sockets"]}" '
            f'cores="{topology["cores"]}" threads="{topology["threads"]}"/>',
            '    <cache mode="passthrough"/>',
            '  </cpu>'
        ]
        return '\n'.join(config)
    
    def _generate_clock_config(self) -> str:
        """Generate clock configuration for Windows"""
        config = [
            '  <clock offset="localtime">',
            '    <timer name="rtc" tickpolicy="catchup"/>',
            '    <timer name="pit" tickpolicy="delay"/>',
            '    <timer name="hpet" present="no"/>',
            '    <timer name="hypervclock" present="yes"/>',
            '  </clock>'
        ]
        return '\n'.join(config)
    
    def _generate_disk_config(self, disk_path: str) -> str:
        """Generate virtio-blk disk configuration"""
        config = [
            f'    <disk type="file" device="disk">',
            f'      <driver name="qemu" type="qcow2" cache="writeback"/>',
            f'      <source file="{disk_path}"/>',
            '      <target dev="vda" bus="virtio"/>',
            '      <address type="pci" domain="0x0000" bus="0x04" slot="0x00" function="0x0"/>',
            '    </disk>'
        ]
        return '\n'.join(config)
    
    def _generate_cdrom_config(self, iso_path: str, dev_name: str) -> str:
        """Generate CD-ROM drive configuration"""
        config = [
            '    <disk type="file" device="cdrom">',
            '      <driver name="qemu" type="raw"/>',
            f'      <source file="{iso_path}"/>',
            f'      <target dev="{dev_name}" bus="sata"/>',
            '      <readonly/>',
            '    </disk>'
        ]
        return '\n'.join(config)
    
    def _generate_network_config(self) -> str:
        """Generate virtio network interface"""
        config = [
            '    <interface type="network">',
            '      <mac address="52:54:00:' + ':'.join([f'{uuid.uuid4().hex[i:i+2]}' for i in range(0, 6, 2)])[:17] + '"/>',
            '      <source network="default"/>',
            '      <model type="virtio"/>',
            '      <address type="pci" domain="0x0000" bus="0x01" slot="0x00" function="0x0"/>',
            '    </interface>'
        ]
        return '\n'.join(config)
    
    def _generate_qxl_graphics(self) -> str:
        """Generate QXL graphics for first boot"""
        config = [
            '    <graphics type="spice" autoport="yes">',
            '      <listen type="address"/>',
            '      <image compression="off"/>',
            '      <gl enable="no"/>',
            '    </graphics>',
            '    <video>',
            '      <model type="qxl" ram="65536" vram="65536" vgamem="16384" heads="1" primary="yes"/>',
            '      <address type="pci" domain="0x0000" bus="0x00" slot="0x01" function="0x0"/>',
            '    </video>',
            '    <audio id="1" type="spice"/>'
        ]
        return '\n'.join(config)
    
    def _generate_pci_hostdev(self, pci_address: str) -> str:
        """Generate PCI hostdev passthrough for GPU"""
        parts = pci_address.split(':')
        domain = parts[0]
        bus = parts[1]
        slot_func = parts[2].split('.')
        slot = slot_func[0]
        function = slot_func[1]
        
        config = [
            '    <hostdev mode="subsystem" type="pci" managed="yes">',
            '      <source>',
            f'        <address domain="0x{domain}" bus="0x{bus}" '
            f'slot="0x{slot}" function="0x{function}"/>',
            '      </source>',
            '      <address type="pci" domain="0x0000" bus="0x07" slot="0x00" function="0x0"/>',
            '    </hostdev>'
        ]
        return '\n'.join(config)
    
    def _generate_console(self) -> str:
        """Generate console and serial ports"""
        config = [
            '    <serial type="pty">',
            '      <target type="isa-serial" port="0">',
            '        <model name="isa-serial"/>',
            '      </target>',
            '    </serial>',
            '    <console type="pty">',
            '      <target type="serial" port="0"/>',
            '    </console>',
            '    <channel type="spicevmc">',
            '      <target type="virtio" name="com.redhat.spice.0"/>',
            '      <address type="virtio-serial" controller="0" bus="0" port="1"/>',
            '    </channel>',
            '    <channel type="unix">',
            '      <target type="virtio" name="org.qemu.guest_agent.0"/>',
            '      <address type="virtio-serial" controller="0" bus="0" port="2"/>',
            '    </channel>'
        ]
        return '\n'.join(config)
    
    def _generate_input_devices(self) -> str:
        """Generate input devices"""
        config = [
            '    <input type="tablet" bus="usb">',
            '      <address type="usb" bus="0" port="1"/>',
            '    </input>',
            '    <input type="mouse" bus="ps2"/>',
            '    <input type="keyboard" bus="ps2"/>'
        ]
        return '\n'.join(config)
    
    def _generate_tpm_device(self) -> str:
        """Generate TPM 2.0 device for Windows 11"""
        config = [
            '    <tpm model="tpm-crb">',
            '      <backend type="emulator" version="2.0"/>',
            '    </tpm>'
        ]
        return '\n'.join(config)
