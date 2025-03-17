import requests
import logging
import time
from fastapi import HTTPException

from config import COMMAND_EXECUTOR_URL, COMMAND_TIMEOUT

logger = logging.getLogger(__name__)

async def execute_command_on_vm(command, vm_id, task_id):
    """Execute a command on a specific VM."""
    try:
        exec_response = requests.post(
            f"{COMMAND_EXECUTOR_URL}/execute/vm",
            json={
                "command": command,
                "vm_id": vm_id,
                "task_id": task_id,
                "timeout_seconds": COMMAND_TIMEOUT
            },
            timeout=COMMAND_TIMEOUT + 5
        )
        
        if exec_response.status_code != 200:
            logger.error(f"Failed to execute command: {exec_response.text}")
            return {
                "command": command,
                "status": "Failed",
                "stdout": None,
                "stderr": f"Failed to execute command: {exec_response.text}",
                "exit_code": -1
            }
            
        command_id = exec_response.json()["id"]
        
        # Wait for command completion
        result = None
        max_attempts = 10
        for attempt in range(max_attempts):
            time.sleep(1)
            
            result_response = requests.get(
                f"{COMMAND_EXECUTOR_URL}/result/{command_id}",
                timeout=5
            )
            
            if result_response.status_code == 200:
                result = result_response.json()
                if result["status"] in ["Completed", "Failed", "TimedOut"]:
                    break
        
        if not result or result["status"] == "Running":
            return {
                "command": command,
                "status": "TimedOut",
                "stdout": None,
                "stderr": "Command execution timed out",
                "exit_code": -1
            }
            
        return result
    except Exception as e:
        logger.error(f"Error executing command '{command}': {str(e)}")
        return {
            "command": command,
            "status": "Failed",
            "stdout": None,
            "stderr": f"Error: {str(e)}",
            "exit_code": -1
        }

async def execute_command_locally(command, execution_engine):
    """Execute a command locally using the execution engine."""
    return execution_engine.execute_command(command)
