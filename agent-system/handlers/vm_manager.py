iimport requests
import logging
from fastapi import HTTPException

from config import VM_MANAGER_URL

logger = logging.getLogger(__name__)

async def create_vm_for_task(task_id):
    """Create a new VM for a task."""
    try:
        vm_response = requests.post(
            f"{VM_MANAGER_URL}/vms",
            json={"task_id": task_id},
            timeout=10
        )
        
        if vm_response.status_code == 200:
            vm_data = vm_response.json()
            logger.info(f"Created VM for task {task_id}: {vm_data['id']}")
            return vm_data
        else:
            logger.error(f"Failed to create VM for task {task_id}: {vm_response.text}")
            return None
    except Exception as e:
        logger.error(f"Error creating VM for task {task_id}: {str(e)}")
        return None

async def reset_vm(vm_id, force=False):
    """Reset an existing VM."""
    try:
        reset_response = requests.post(
            f"{VM_MANAGER_URL}/vms/{vm_id}/reset",
            json={"force": force},
            timeout=10
        )
        
        if reset_response.status_code == 200:
            logger.info(f"Reset VM {vm_id}")
            return reset_response.json()
        else:
            logger.error(f"Failed to reset VM {vm_id}: {reset_response.text}")
            return None
    except Exception as e:
        logger.error(f"Error resetting VM {vm_id}: {str(e)}")
        return None

async def get_vm_details(vm_id):
    """Get details about a VM."""
    try:
        vm_response = requests.get(f"{VM_MANAGER_URL}/vms/{vm_id}", timeout=5)
        if vm_response.status_code != 200:
            raise HTTPException(status_code=404, detail="VM not found in VM Manager")
        
        return vm_response.json()
    except Exception as e:
        logger.error(f"Error getting VM details for {vm_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error connecting to VM Manager: {str(e)}")
