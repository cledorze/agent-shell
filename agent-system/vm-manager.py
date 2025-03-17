import logging
import uuid
import time
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class VMManager:
    """VM Manager with comprehensive connection handling."""
    
    def __init__(self):
        self.available = False
        self.connection_type = "none"
        self.conn = None
        
        # Try direct libvirt API connection
        try:
            import libvirt
            uri = os.environ.get('LIBVIRT_URI', 'qemu:///system')
            logger.info(f"Attempting to connect to libvirt using URI: {uri}")
            
            self.conn = libvirt.open(uri)
            if self.conn:
                self.available = True
                self.connection_type = "libvirt-api"
                hypervisor = self.conn.getType()
                version = self.conn.getVersion()
                lib_version = self.conn.getLibVersion()
                logger.info(f"Connected to libvirt API. Hypervisor: {hypervisor}, Version: {version}, libvirt: {lib_version}")
            else:
                logger.warning(f"Failed to connect to libvirt using URI: {uri}")
        except ImportError:
            logger.warning("libvirt Python module not available")
        except Exception as e:
            logger.warning(f"Failed to connect to libvirt API: {str(e)}")
            
            # Try CLI as fallback
            try:
                import subprocess
                result = subprocess.run(
                    ["virsh", "-c", "qemu:///system", "list"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    self.available = True
                    self.connection_type = "virsh-cli"
                    logger.info(f"Using virsh CLI for VM management")
                else:
                    logger.warning(f"Failed to use virsh CLI: {result.stderr}")
            except Exception as cli_err:
                logger.warning(f"Failed to use virsh CLI: {str(cli_err)}")
        
        if not self.available:
            logger.warning("VM management will be simulated (no libvirt access)")
    
    async def create_vm_for_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Create a VM for a specific task."""
        vm_id = str(uuid.uuid4())
        vm_name = f"agent-vm-{task_id[:8]}"
        
        logger.info(f"Creating VM for task {task_id} (connection: {self.connection_type})")
        
        # For development, return simulated data
        return {
            "id": vm_id,
            "name": vm_name,
            "task_id": task_id,
            "state": "running",
            "connection_type": self.connection_type,
            "ip_address": "192.168.122.100",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ssh_username": "agent",
            "ssh_password": "password"
        }
    
    async def get_vm_details(self, vm_id: str) -> Optional[Dict[str, Any]]:
        """Get details about a VM."""
        logger.info(f"Getting details for VM {vm_id}")
        
        return {
            "id": vm_id,
            "name": f"agent-vm-{vm_id[:8]}",
            "state": "running",
            "connection_type": self.connection_type,
            "ip_address": "192.168.122.100",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ssh_username": "agent",
            "ssh_password": "password"
        }
    
    async def reset_vm(self, vm_id: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """Reset a VM."""
        logger.info(f"Resetting VM {vm_id} (force={force})")
        
        return {
            "status": "success",
            "message": f"VM {vm_id} has been reset",
            "connection_type": self.connection_type,
            "vm_id": vm_id
        }
    
    def is_available(self) -> bool:
        """Check if VM Manager is available."""
        return self.available
    
    def get_status(self) -> Dict[str, Any]:
        """Get VM Manager status."""
        return {
            "available": self.available,
            "connection_type": self.connection_type
        }
    
    def __del__(self):
        """Close libvirt connection on cleanup."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Closed libvirt connection")
            except:
                pass
