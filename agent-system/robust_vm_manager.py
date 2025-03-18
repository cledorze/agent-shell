import logging
import uuid
import time
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class RobustVMManager:
    """
    Bridge to the VM Manager service for Python components.
    Makes HTTP requests to the Go VM Manager to create and manage VMs.
    """
    
    def __init__(self, vm_manager_url: str = None):
        """
        Initialize the VM Manager bridge.
        
        Args:
            vm_manager_url: URL of the VM Manager service
        """
        self.vm_manager_url = vm_manager_url or "http://vm-manager:8083"
        self.available = self._check_availability()
        
        logger.info(f"VM Manager bridge initialized: {self.vm_manager_url} (available: {self.available})")
    
    def _check_availability(self) -> bool:
        """Check if the VM Manager is available."""
        try:
            response = requests.get(f"{self.vm_manager_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"VM Manager is not available: {str(e)}")
            return False
    
    async def create_vm_for_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Create a VM for a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            VM information or None if creation failed
        """
        if not self.available:
            self.available = self._check_availability()
            if not self.available:
                logger.warning("VM Manager not available, returning simulated VM")
                # Return simulated VM info for development
                vm_id = str(uuid.uuid4())
                return {
                    "id": vm_id,
                    "name": f"sim-vm-{task_id[:8]}",
                    "task_id": task_id,
                    "state": "running",
                    "connection_type": "simulated",
                    "ip_address": "192.168.122.100",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ssh_username": "agent",
                    "ssh_password": "simulated-password"
                }
        
        try:
            response = requests.post(
                f"{self.vm_manager_url}/vms",
                json={"task_id": task_id},
                timeout=10
            )
            
            if response.status_code == 200:
                vm_data = response.json()
                logger.info(f"Created VM for task {task_id}: {vm_data['id']}")
                return vm_data
            else:
                logger.error(f"Failed to create VM for task {task_id}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating VM for task {task_id}: {str(e)}")
            return None
    
    async def get_vm_details(self, vm_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details about a VM.
        
        Args:
            vm_id: VM identifier
            
        Returns:
            VM details or None if retrieval failed
        """
        if not self.available:
            self.available = self._check_availability()
            if not self.available:
                logger.warning("VM Manager not available, returning simulated VM details")
                return {
                    "id": vm_id,
                    "name": f"sim-vm-{vm_id[:8]}",
                    "state": "running", 
                    "connection_type": "simulated",
                    "ip_address": "192.168.122.100",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ssh_username": "agent",
                    "ssh_password": "simulated-password"
                }
        
        try:
            response = requests.get(f"{self.vm_manager_url}/vms/{vm_id}", timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get VM details: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting VM details for {vm_id}: {str(e)}")
            return None
    
    async def get_vm_by_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get VM details for a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            VM details or None if retrieval failed
        """
        if not self.available:
            self.available = self._check_availability()
            if not self.available:
                logger.warning("VM Manager not available, returning simulated VM details")
                return {
                    "id": str(uuid.uuid4()),
                    "name": f"sim-vm-{task_id[:8]}",
                    "task_id": task_id,
                    "state": "running", 
                    "connection_type": "simulated",
                    "ip_address": "192.168.122.100",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ssh_username": "agent",
                    "ssh_password": "simulated-password"
                }
        
        try:
            response = requests.get(f"{self.vm_manager_url}/tasks/{task_id}/vm", timeout=5)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # No VM exists for this task yet
                return None
            else:
                logger.error(f"Failed to get VM for task {task_id}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting VM for task {task_id}: {str(e)}")
            return None
    
    async def reset_vm(self, vm_id: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Reset a VM to a clean state.
        
        Args:
            vm_id: VM identifier
            force: Whether to force reset
            
        Returns:
            Reset response or None if reset failed
        """
        if not self.available:
            self.available = self._check_availability()
            if not self.available:
                logger.warning("VM Manager not available, simulating VM reset")
                return {
                    "status": "success",
                    "message": f"VM {vm_id} has been reset (simulated)",
                    "connection_type": "simulated",
                    "vm_id": vm_id
                }
        
        try:
            response = requests.post(
                f"{self.vm_manager_url}/vms/{vm_id}/reset",
                json={"force": force},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Reset VM {vm_id}")
                return response.json()
            else:
                logger.error(f"Failed to reset VM {vm_id}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error resetting VM {vm_id}: {str(e)}")
            return None
    
    async def destroy_vm(self, vm_id: str) -> Optional[Dict[str, Any]]:
        """
        Destroy a VM completely.
        
        Args:
            vm_id: VM identifier
            
        Returns:
            Destroy response or None if destruction failed
        """
        if not self.available:
            self.available = self._check_availability()
            if not self.available:
                logger.warning("VM Manager not available, simulating VM destruction")
                return {
                    "status": "success", 
                    "message": f"VM {vm_id} has been destroyed (simulated)",
                    "connection_type": "simulated",
                    "vm_id": vm_id
                }
        
        try:
            response = requests.delete(f"{self.vm_manager_url}/vms/{vm_id}", timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Destroyed VM {vm_id}")
                return response.json()
            else:
                logger.error(f"Failed to destroy VM {vm_id}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error destroying VM {vm_id}: {str(e)}")
            return None
    
    async def list_vms(self) -> List[Dict[str, Any]]:
        """
        List all VMs.
        
        Returns:
            List of VMs or empty list if retrieval failed
        """
        if not self.available:
            self.available = self._check_availability()
            if not self.available:
                logger.warning("VM Manager not available, returning simulated VM list")
                return [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "sim-vm-example",
                        "state": "running", 
                        "connection_type": "simulated",
                        "ip_address": "192.168.122.100",
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "ssh_username": "agent",
                        "ssh_password": "simulated-password"
                    }
                ]
        
        try:
            response = requests.get(f"{self.vm_manager_url}/vms", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("vms", [])
            else:
                logger.error(f"Failed to list VMs: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error listing VMs: {str(e)}")
            return []
    
    def is_available(self) -> bool:
        """Check if VM Manager is available."""
        if not self.available:
            self.available = self._check_availability()
        return self.available
