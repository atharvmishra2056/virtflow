"""
Core libvirt connection and VM management
"""

import libvirt
from typing import List, Optional, Dict
from utils.logger import logger
import config
import xml.etree.ElementTree as ET # <-- NEW: Import ET

# --- NEW: Define our custom XML namespace ---
VIRTFLOW_XML_NS = "https://virtflow.org/xmlns/domain/1.0"
ET.register_namespace("virtflow", VIRTFLOW_XML_NS)


class LibvirtManager:
    """Manages libvirt connection and basic operations"""
    
    def __init__(self, uri: str = None):
        """
        Initialize libvirt connection
        
        Args:
            uri: libvirt connection URI (default: qemu:///system)
        """
        self.uri = uri or config.DEFAULT_LIBVIRT_URI
        self._conn: Optional[libvirt.virConnect] = None
        self.connect()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
    
    def connect(self) -> bool:
        """
        Establish connection to libvirt daemon
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self._conn and self._conn.isAlive():
                return True
            
            logger.info(f"Connecting to libvirt at {self.uri}")
            self._conn = libvirt.open(self.uri)
            
            if self._conn is None:
                logger.error("Failed to open connection to libvirt")
                return False
            
            logger.info(f"Connected to hypervisor: {self._conn.getType()}")
            logger.info(f"Hypervisor version: {self._conn.getVersion()}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Libvirt connection error: {e}")
            return False
    
    def disconnect(self):
        """Close libvirt connection"""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Disconnected from libvirt")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self._conn = None
    
    @property
    def connection(self) -> Optional[libvirt.virConnect]:
        """Get active libvirt connection"""
        if not self._conn or not self._conn.isAlive():
            self.connect()
        return self._conn
    
    def list_all_vms(self) -> List[libvirt.virDomain]:
        """
        Get list of all VMs (running and stopped)
        
        Returns:
            List of libvirt domain objects
        """
        try:
            if not self.connection:
                return []
            
            domains = self.connection.listAllDomains()
            logger.debug(f"Found {len(domains)} VMs")
            return domains
            
        except libvirt.libvirtError as e:
            logger.error(f"Error listing VMs: {e}")
            return []
    
    def get_vm_by_name(self, name: str) -> Optional[libvirt.virDomain]:
        """
        Get VM by name
        
        Args:
            name: VM name
            
        Returns:
            libvirt domain object or None
        """
        try:
            return self.connection.lookupByName(name)
        except libvirt.libvirtError:
            logger.warning(f"VM '{name}' not found")
            return None
    
    def get_vm_by_uuid(self, uuid: str) -> Optional[libvirt.virDomain]:
        """
        Get VM by UUID
        
        Args:
            uuid: VM UUID string
            
        Returns:
            libvirt domain object or None
        """
        try:
            return self.connection.lookupByUUIDString(uuid)
        except libvirt.libvirtError:
            logger.warning(f"VM with UUID '{uuid}' not found")
            return None
    
    def create_vm_from_xml(self, xml: str) -> Optional[libvirt.virDomain]:
        """
        Create and define a new VM from XML
        
        Args:
            xml: libvirt domain XML string
            
        Returns:
            libvirt domain object or None
        """
        try:
            domain = self.connection.defineXML(xml)
            logger.info(f"VM '{domain.name()}' created successfully")
            return domain
        except libvirt.libvirtError as e:
            logger.error(f"Failed to create VM: {e}")
            return None
    
    def delete_vm(self, domain: libvirt.virDomain, remove_storage: bool = True) -> bool:
        """
        Delete a VM
        
        Args:
            domain: libvirt domain object
            remove_storage: Also remove associated storage
            
        Returns:
            bool: Success status
        """
        try:
            vm_name = domain.name()
            
            # Stop VM if running
            if domain.isActive():
                logger.info(f"Stopping VM '{vm_name}' before deletion")
                domain.destroy()
            
            # Remove storage volumes if requested
            if remove_storage:
                self._remove_vm_storage(domain)
            
            # Undefine VM
            domain.undefine()
            logger.info(f"VM '{vm_name}' deleted successfully")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to delete VM: {e}")
            return False
    
    def _remove_vm_storage(self, domain: libvirt.virDomain):
        """Remove storage volumes associated with VM"""
        try:
            xml_desc = domain.XMLDesc(0)
            # Parse XML and find disk paths
            # This is a simplified version - full implementation would parse XML
            logger.debug(f"Storage cleanup for {domain.name()}")
        except Exception as e:
            logger.warning(f"Could not remove storage: {e}")
    
    def get_storage_pool(self, pool_name: str = "default"):
        """Get storage pool by name"""
        try:
            return self.connection.storagePoolLookupByName(pool_name)
        except libvirt.libvirtError:
            logger.warning(f"Storage pool '{pool_name}' not found")
            return None
    
    def _get_virtflow_metadata_node(self, root: ET.Element) -> ET.Element:
        """Finds or creates the <metadata> and <virtflow:virtflow> nodes."""
        metadata_node = root.find("metadata")
        if metadata_node is None:
            metadata_node = ET.SubElement(root, "metadata")
        
        # Note: ET.find() requires the namespace URI in curly braces
        virtflow_node = metadata_node.find(f"{{{VIRTFLOW_XML_NS}}}virtflow")
        if virtflow_node is None:
            virtflow_node = ET.SubElement(metadata_node, f"{{{VIRTFLOW_XML_NS}}}virtflow")
        
        return virtflow_node

    # --- NEW: Get Display Preference ---
    def get_display_preference(self, domain: libvirt.virDomain) -> str:
        """
        Reads the preferred display type from VM metadata.
        Returns 'spice' or 'looking-glass'. Defaults to 'spice'.
        """
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            virtflow_node = root.find(f".//{{{VIRTFLOW_XML_NS}}}virtflow")
            
            if virtflow_node is not None:
                display_node = virtflow_node.find(f"{{{VIRTFLOW_XML_NS}}}display")
                if display_node is not None and display_node.get('type'):
                    return display_node.get('type')
        except Exception as e:
            logger.error(f"Could not read display preference: {e}")
        
        return "spice" # Default

    # --- NEW: Set Display Preference ---
    def set_display_preference(self, domain: libvirt.virDomain, preference: str):
        """
        Writes the preferred display type to VM metadata.
        'preference' should be 'spice' or 'looking-glass'.
        """
        if preference not in ["spice", "looking-glass"]:
            logger.warning(f"Invalid display preference: {preference}")
            return

        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            virtflow_node = self._get_virtflow_metadata_node(root)
            
            display_node = virtflow_node.find(f"{{{VIRTFLOW_XML_NS}}}display")
            if display_node is None:
                display_node = ET.SubElement(virtflow_node, f"{{{VIRTFLOW_XML_NS}}}display")
                
            display_node.set("type", preference)
            
            # Re-define the VM with the updated XML
            new_xml = ET.tostring(root, encoding="unicode")
            self.connection.defineXML(new_xml)
            logger.info(f"Set display preference for {domain.name()} to {preference}")
            
        except Exception as e:
            logger.error(f"Failed to set display preference: {e}")

    # --- TASKS 2.2 & 2.3: New generic settings methods ---
    def set_vm_setting(self, domain: libvirt.virDomain, key: str, value: str):
        """Saves a generic key-value setting to the VM's metadata."""
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            virtflow_node = self._get_virtflow_metadata_node(root)
            
            setting_node = virtflow_node.find(f"{{{VIRTFLOW_XML_NS}}}setting[@key='{key}']")
            if setting_node is None:
                setting_node = ET.SubElement(virtflow_node, f"{{{VIRTFLOW_XML_NS}}}setting")
                setting_node.set("key", key)
                
            setting_node.set("value", value)
            
            new_xml = ET.tostring(root, encoding="unicode")
            self.connection.defineXML(new_xml)
            logger.debug(f"Set VM setting for {domain.name()}: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Failed to set VM setting '{key}': {e}")

    def update_core_hardware(self, domain: libvirt.virDomain, vcpus: int, memory_mb: int) -> bool:
        """Applies core hardware changes (RAM, CPU) to a defined (non-running) VM."""
        if domain.isActive():
            logger.error("Cannot change core hardware while VM is running.")
            return False
        
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            # Update VCPUs
            vcpu_node = root.find("vcpu")
            if vcpu_node is not None:
                vcpu_node.text = str(vcpus)
            
            # Update Memory (libvirt uses KiB)
            memory_node = root.find("memory")
            if memory_node is not None:
                memory_node.text = str(memory_mb * 1024)
                memory_node.set("unit", "KiB")
            
            # Update Current Memory (optional, but good practice)
            current_memory_node = root.find("currentMemory")
            if current_memory_node is not None:
                current_memory_node.text = str(memory_mb * 1024)
                current_memory_node.set("unit", "KiB")
                
            # Re-define the VM
            new_xml = ET.tostring(root, encoding="unicode")
            self.connection.defineXML(new_xml)
            logger.info(f"Updated core hardware for {domain.name()}: {vcpus} VCPUs, {memory_mb} MB RAM")
            return True
        except Exception as e:
            logger.error(f"Failed to update core hardware: {e}")
            return False

    def get_all_vm_settings(self, domain: libvirt.virDomain) -> Dict[str, str]:
        """Retrieves all saved settings from the VM's metadata AND live config."""
        settings = {}
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            # 1. Read live hardware values
            settings["vcpus"] = root.find("vcpu").text or "1"
            settings["memory_mb"] = str(int(root.find("memory").text or "1024") // 1024)
            
            # VRAM (from QXL or VirtIO)
            qxl_vram = root.find(".//video/model[@type='qxl']")
            virtio_vram = root.find(".//video/model[@type='virtio']")
            if qxl_vram is not None and qxl_vram.get("vram"):
                # qxl vram is in KiB
                settings["vram"] = str(int(qxl_vram.get("vram")) // 1024)
            elif virtio_vram is not None and virtio_vram.get("vram"):
                # virtio vram is in KiB
                settings["vram"] = str(int(virtio_vram.get("vram")) // 1024)
            else:
                settings["vram"] = "64" # Default if not found
            
            # 3D Accel
            accel = root.find(".//video/model/acceleration")
            settings["3d_accel"] = "true" if (accel is not None and accel.get("accel3d") == "yes") else "false"
            
            # TPM
            settings["tpm_enabled"] = "true" if root.find(".//tpm") is not None else "false"

            # 2. Read saved metadata settings
            virtflow_node = root.find(f".//{{{VIRTFLOW_XML_NS}}}virtflow")
            if virtflow_node is not None:
                for setting in virtflow_node.findall(f"{{{VIRTFLOW_XML_NS}}}setting"):
                    key = setting.get("key")
                    value = setting.get("value")
                    if key and key not in settings: # Metadata overrides only if not live
                        settings[key] = value
                        
        except Exception as e:
            logger.error(f"Could not read VM settings: {e}")
        
        return settings
    # --- END TASKS 2.2 & 2.3 ---

    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()