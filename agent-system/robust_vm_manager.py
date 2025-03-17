import logging
import uuid
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RobustVMManager:
    """VM Manager with graceful fallback capabilities."""
    
    def __init__(self):
        self.available = False
        self.connection_type = "none"
        
        # Try to initialize libvirt connection
        try:
            # First attempt direct Python bindings
            import libvirt
            self.conn = libvirt.open("qemu:///system")
            
            if self.conn:
                self.available = True
                self.connection_type = "libvirt-api"
                hypervisor = self.conn.getType()
                version = self.conn.getVersion()
                logger.info(f"Connected to libvirt API. Hypervisor: {hypervisor}, Version: {version}")
            else:
                logger.warning("Failed to connect to libvirt (conn is None)")
        except ImportError:
            logger.warning("libvirt Python module not available")
        except Exception as e:
            logger.warning(f"Failed to connect to libvirt API: {str(e)}")
            
            # Try CLI access as fallback
            try:
                import subprocess
                result = subprocess.run(
                    ["virsh", "--version"], 
                    capture_output=True, 
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    self.available = True
                    self.connection_type = "virsh-cli"
                    logger.info(f"Using virsh CLI. Version: {result.stdout.strip()}")
            except Exception as cli_err:
                logger.warning(f"Failed to use virsh CLI: {str(cli_err)}")
        
        if not self.available:
            logger.warning("VM management will be simulated (no libvirt access)")
    
    async def create_vm_for_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Create a VM for a specific task."""
        vm_id = str(uuid.uuid4())
        vm_name = f"agent-vm-{task_id[:8]}"
        
        logger.info(f"Creating VM for task {task_id} (connection: {self.connection_type})")
        
        # In a production implementation, this would create an actual VM
        # For now, return simulated data
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
    
    def __del__(self):
        """Close libvirt connection if it exists."""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
                logger.info("Closed libvirt connection")
            except:
                pass
