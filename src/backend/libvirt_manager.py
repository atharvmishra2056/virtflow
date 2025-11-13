"""
Core libvirt connection and VM management
"""

import libvirt
from typing import List, Optional, Dict
from utils.logger import logger
import config


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
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
