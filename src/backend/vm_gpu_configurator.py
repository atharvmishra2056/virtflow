import time
import xml.etree.ElementTree as ET
from utils.logger import logger
from backend.vfio_manager import VFIOManager

class VMGPUConfigurator:
    """
    Configures VMs for GPU passthrough (libvirt hook compatible)
    Pass `LibvirtManager` instance to constructor.
    """
    def __init__(self, libvirt_manager):
        self.libvirt_manager = libvirt_manager
        self.vfio_manager = VFIOManager()

    def enable_gpu_passthrough(self, vm_name: str, gpu) -> bool:
        """
        Enable GPU passthrough for VM.
        1. Bind GPU to VFIO driver
        2. Modify VM XML to add GPU hostdev
        3. Remove all virtual display devices
        """
        logger.info(f"Enabling GPU passthrough for '{vm_name}'")
        try:
            domain = self.libvirt_manager.get_vm_by_name(vm_name)
            if domain is None:
                raise RuntimeError(f"VM '{vm_name}' not found")
            
            # 1. STOP VM IF RUNNING
            if domain.isActive():
                logger.info(f"Stopping VM '{vm_name}'...")
                domain.destroy()
                time.sleep(2)
            
            # 2. BIND GPU TO VFIO (critical step!)
            logger.info(f"Binding {gpu.full_name} to VFIO driver...")
            if not self.vfio_manager.bind_gpu_to_vfio(gpu):
                raise RuntimeError("Failed to bind GPU to VFIO driver")
            logger.info("GPU successfully bound to VFIO")
            
            # 3. Parse domain XML
            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)
            devices = root.find('devices')
            
            if devices is not None:
                # Remove ALL audio devices first (before graphics)
                for audio in list(devices.findall('audio')):
                    logger.info(f"Removing audio device {audio.get('id')}")
                    devices.remove(audio)
                
                # Remove all sound devices
                for sound in list(devices.findall('sound')):
                    model = sound.get('model')
                    logger.info(f"Removing sound device {model}")
                    devices.remove(sound)
                
                # Keep SPICE graphics for integrated viewing
                has_spice = False
                for graphics in list(devices.findall('graphics')):
                    if graphics.get('type') == 'spice':
                        has_spice = True
                        logger.info("Keeping SPICE graphics for integrated viewing")
                
                # Add SPICE graphics if not present
                if not has_spice:
                    logger.info("Adding SPICE graphics for integrated viewing")
                    graphics = ET.SubElement(devices, 'graphics')
                    graphics.set('type', 'spice')
                    graphics.set('autoport', 'yes')
                    graphics.set('listen', '127.0.0.1')
                    listen = ET.SubElement(graphics, 'listen')
                    listen.set('type', 'address')
                    listen.set('address', '127.0.0.1')
                
                # Keep QXL video device for SPICE (needed for display)
                has_video = any(devices.findall('video'))
                if not has_video:
                    logger.info("Adding QXL video device for SPICE display")
                    video = ET.SubElement(devices, 'video')
                    model = ET.SubElement(video, 'model')
                    model.set('type', 'qxl')
                    model.set('ram', '65536')
                    model.set('vram', '65536')
                    model.set('vgamem', '16384')
                    model.set('heads', '1')
                    model.set('primary', 'yes')
                
                # Remove all channel devices (spicevmc, virtio, etc)
                for channel in list(devices.findall('channel')):
                    target = channel.find('target')
                    if target is not None:
                        logger.info(f"Removing channel device {target.get('type')}")
                        devices.remove(channel)
                
                # Remove all redirdev (spice USB redirection)
                for redirdev in list(devices.findall('redirdev')):
                    logger.info(f"Removing redirdev {redirdev.get('type')}")
                    devices.remove(redirdev)
                
                # Remove all smartcard (spice)
                for smartcard in list(devices.findall('smartcard')):
                    logger.info("Removing smartcard")
                    devices.remove(smartcard)
                
                # Remove tablet input device (spice)
                for inputdev in list(devices.findall('input')):
                    if inputdev.get('type') == 'tablet' and inputdev.get('bus') == 'usb':
                        logger.info("Removing input tablet device")
                        devices.remove(inputdev)
                
                # Remove existing GPU hostdevs (if any) to avoid duplicates
                gpu_pci_addresses = [dev.address for dev in gpu.all_devices]
                for hostdev in list(devices.findall('hostdev')):
                    if hostdev.get('type') == 'pci':
                        source = hostdev.find('source')
                        if source is not None:
                            address = source.find('address')
                            if address is not None:
                                # Reconstruct PCI address from XML
                                domain = address.get('domain', '0x0000').replace('0x', '')
                                bus = address.get('bus', '0x00').replace('0x', '')
                                slot = address.get('slot', '0x00').replace('0x', '')
                                func = address.get('function', '0x0').replace('0x', '')
                                pci_addr = f"{domain}:{bus}:{slot}.{func}"
                                
                                # Check if this matches our GPU devices
                                if pci_addr in gpu_pci_addresses:
                                    logger.info(f"Removing existing hostdev for {pci_addr}")
                                    devices.remove(hostdev)
                
                # Add GPU hostdevs
                for pci_device in gpu.all_devices:
                    domain_s, bus, slot_func = pci_device.address.split(':')
                    slot, func = slot_func.split('.')
                    hostdev = ET.Element('hostdev')
                    hostdev.set('mode', 'subsystem')
                    hostdev.set('type', 'pci')
                    hostdev.set('managed', 'no')  # We manually manage VFIO binding
                    source = ET.SubElement(hostdev, 'source')
                    address = ET.SubElement(source, 'address')
                    address.set('domain', f"0x{domain_s}")
                    address.set('bus', f"0x{bus}")
                    address.set('slot', f"0x{slot}")
                    address.set('function', f"0x{func}")
                    devices.append(hostdev)
                    logger.info(f"Added hostdev for {pci_device.address}")
            
            # 4. Write back and redefine
            new_xml = ET.tostring(root, encoding='unicode')
            self.libvirt_manager.connection.defineXML(new_xml)
            logger.info(f"GPU passthrough enabled for '{vm_name}'. GPU will be available on next start.")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to enable GPU passthrough: {e}")
            return False
    
    def disable_gpu_passthrough(self, vm_name: str, gpu) -> bool:
        """
        Disable GPU passthrough and restore GPU to host.
        1. Stop VM if running
        2. Remove GPU hostdev from XML
        3. Restore virtual display devices
        4. Unbind GPU from VFIO and restore to host driver
        """
        logger.info(f"Disabling GPU passthrough for '{vm_name}'")
        try:
            domain = self.libvirt_manager.get_vm_by_name(vm_name)
            if domain is None:
                raise RuntimeError(f"VM '{vm_name}' not found")
            
            # 1. STOP VM IF RUNNING
            if domain.isActive():
                logger.info(f"Stopping VM '{vm_name}'...")
                domain.destroy()
                time.sleep(2)
            
            # 2. Parse domain XML
            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)
            devices = root.find('devices')
            
            if devices is not None:
                # Remove all GPU hostdevs
                gpu_addresses = [dev.address for dev in gpu.all_devices]
                for hostdev in list(devices.findall('hostdev')):
                    if hostdev.get('type') == 'pci':
                        source = hostdev.find('source')
                        if source is not None:
                            address = source.find('address')
                            if address is not None:
                                # Reconstruct PCI address
                                domain_hex = address.get('domain', '0x0000')
                                bus_hex = address.get('bus', '0x00')
                                slot_hex = address.get('slot', '0x00')
                                func_hex = address.get('function', '0x0')
                                
                                pci_addr = f"{int(domain_hex, 16):04x}:{int(bus_hex, 16):02x}:{int(slot_hex, 16):02x}.{int(func_hex, 16)}"
                                
                                if pci_addr in gpu_addresses:
                                    logger.info(f"Removing hostdev for {pci_addr}")
                                    devices.remove(hostdev)
                
                # Add back basic graphics (VNC)
                graphics = ET.SubElement(devices, 'graphics')
                graphics.set('type', 'vnc')
                graphics.set('port', '-1')
                graphics.set('autoport', 'yes')
                logger.info("Added VNC graphics")
                
                # Add back video device (QXL)
                video = ET.SubElement(devices, 'video')
                model = ET.SubElement(video, 'model')
                model.set('type', 'qxl')
                model.set('ram', '65536')
                model.set('vram', '65536')
                model.set('vgamem', '16384')
                model.set('heads', '1')
                logger.info("Added QXL video device")
            
            # 3. Write back and redefine
            new_xml = ET.tostring(root, encoding='unicode')
            self.libvirt_manager.connection.defineXML(new_xml)
            logger.info(f"Removed GPU hostdev from '{vm_name}' XML")
            
            # 4. UNBIND GPU FROM VFIO AND RESTORE TO HOST
            logger.info(f"Restoring {gpu.full_name} to host driver...")
            if not self.vfio_manager.unbind_gpu_from_vfio(gpu):
                logger.warning("Failed to restore GPU to host driver")
            else:
                logger.info("GPU successfully restored to host")
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to disable GPU passthrough: {e}")
            return False
