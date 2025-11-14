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
    
    # --- NEW: Get Display Preference ---
    def get_display_preference(self, domain: libvirt.virDomain) -> str:
        """
        Reads the preferred display type from VM metadata.
        Returns 'spice' or 'looking-glass'. Defaults to 'spice'.
        """
        try:
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            # Find our custom metadata tag
            # Note: ET.find() requires the namespace URI in curly braces
            display_node = root.find(f".//{{{VIRTFLOW_XML_NS}}}display")
            
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
            
            metadata_node = root.find("metadata")
            if metadata_node is None:
                metadata_node = ET.SubElement(root, "metadata")
            
            # Find or create our virtflow node
            virtflow_node = metadata_node.find(f"{{{VIRTFLOW_XML_NS}}}virtflow")
            if virtflow_node is None:
                virtflow_node = ET.SubElement(metadata_node, f"{{{VIRTFLOW_XML_NS}}}virtflow")
            
            # Find or create the display node
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
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
