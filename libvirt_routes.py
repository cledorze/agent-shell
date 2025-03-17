from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
import uuid
import requests
import logging
from datetime import datetime

from config import KNOWLEDGE_SYSTEM_URL, COMMAND_EXECUTOR_URL, logger
from models.models import TaskRequest, TaskStatus, ResetVMRequest
from api.ui_handler import serve_frontend
from libvirt_manager import LibvirtManager

router = APIRouter()

# Initialize the libvirt VM manager
vm_manager = LibvirtManager()

# Dependencies for components
async def get_components():
    from main import command_generator, execution_engine, state_manager, llm_service
    return command_generator, execution_engine, state_manager, llm_service

@router.get("/", response_class=HTMLResponse)
async def root():
    return serve_frontend()

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    # Get components
    command_generator, execution_engine, state_manager, llm_service = await get_components()
    
    # Check knowledge system health
    knowledge_system_healthy = False
    try:
        knowledge_response = requests.get(f"{KNOWLEDGE_SYSTEM_URL}/health", timeout=2)
        knowledge_system_healthy = knowledge_response.status_code == 200
    except Exception:
        logger.warning("Knowledge System health check failed")
    
    # Check command executor health
    command_executor_healthy = False
    try:
        executor_response = requests.get(f"{COMMAND_EXECUTOR_URL}/health", timeout=2)
        command_executor_healthy = executor_response.status_code == 200
    except Exception:
        logger.warning("Command Executor health check failed")
    
    return {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "vm_manager": "healthy" if vm_manager.available else "unhealthy",
            "knowledge_system": "healthy" if knowledge_system_healthy else "unhealthy",
            "command_executor": "healthy" if command_executor_healthy else "unhealthy",
            "state_manager": "healthy",
            "execution_engine": "healthy",
            "command_generator": "healthy",
            "llm_service": "healthy" if llm_service.api_key else "missing API key"
        }
    }

@router.post("/api/tasks", response_model=TaskStatus)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new task and start processing it."""
    try:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Log the task
        logger.info(f"Received task: {task_request.task}")
        
        # Get components
        command_generator, execution_engine, state_manager, llm_service = await get_components()
        
        # Create execution state
        state = state_manager.create_state(request_id, task_request.task)
        
        # Create VM if execution is requested
        if task_request.execute:
            vm_data = await vm_manager.create_vm_for_task(request_id)
            if vm_data:
                # Store VM info in state
                state_manager.set_variable(request_id, "vm_id", vm_data["id"])
                state_manager.set_variable(request_id, "vm_info", vm_data)
        
        # Start processing in the background
        background_tasks.add_task(
            process_task,
            task_id=request_id,
            task=task_request.task,
            execute=task_request.execute,
            command_generator=command_generator,
            execution_engine=execution_engine,
            state_manager=state_manager
        )
        
        # Return status
        return {
            "request_id": request_id,
            "status": "accepted",
            "message": "Task has been accepted and is being processed",
            "details": {"estimated_completion_time": task_request.timeout or 300}
        }
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to create task",
                "message": str(e)
            }
        )

async def process_task(task_id, task, execute, command_generator, execution_engine, state_manager):
    """Process a task and execute commands if requested."""
    try:
        # Update state to processing
        state = state_manager.get_state(task_id)
        state.status = "running"
        state_manager.save_state(state)
        
        # Generate execution plan
        logger.info(f"Task {task_id}: Generating execution plan")
        plan = command_generator.generate_execution_plan(task)
        
        # Update state with plan
        state_manager.update_plan(task_id, plan)
        
        if execute:
            # Execute the plan
            logger.info(f"Task {task_id}: Executing plan")
            result = execution_engine.execute_plan(plan)
            success = result.get("success", False)
        else:
            # Just mark as completed without execution
            success = True
        
        # Mark as completed
        state_manager.complete_task(task_id, success)
            
        logger.info(f"Task {task_id}: Processing completed")
            
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        state_manager.complete_task(task_id, False)

@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    try:
        # Get components
        _, _, state_manager, _ = await get_components()
        
        state = state_manager.get_state(task_id)
        if not state:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id}
            )
        
        # Convert state to response format
        response = {
            "request_id": task_id,
            "task": state.task,
            "status": state.status,
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "start_time": state.start_time,
            "end_time": state.end_time
        }
        
        # Add executed commands if available
        if hasattr(state, 'executed_commands') and state.executed_commands:
            response["executed_commands"] = state.executed_commands
        
        # Add command outputs if available
        if hasattr(state, 'command_outputs') and state.command_outputs:
            response["command_outputs"] = state.command_outputs
        
        # Add execution plan if available
        if hasattr(state, 'execution_plan') and state.execution_plan:
            response["execution_plan"] = state.execution_plan
        
        # Add VM info if available
        vm_id = state_manager.get_variable(task_id, "vm_id")
        if vm_id:
            response["vm_id"] = vm_id
            
            # Add basic VM info
            vm_info = state_manager.get_variable(task_id, "vm_info")
            if vm_info:
                response["vm_info"] = {
                    "id": vm_info.get("id"),
                    "name": vm_info.get("name"),
                    "state": vm_info.get("state")
                }
        
        return response
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get task status",
                "message": str(e)
            }
        )

@router.get("/api/tasks/{task_id}/commands")
async def get_task_commands(task_id: str):
    """Get the commands for a specific task."""
    try:
        # Get components
        _, _, state_manager, _ = await get_components()
        
        state = state_manager.get_state(task_id)
        if not state:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id}
            )
        
        # Extract commands from execution plan
        commands = []
        if hasattr(state, 'execution_plan') and state.execution_plan and "steps" in state.execution_plan:
            for step in state.execution_plan["steps"]:
                if "commands" in step:
                    commands.extend(step["commands"])
        
        return {
            "request_id": task_id,
            "task": state.task,
            "status": state.status,
            "commands": commands,
            "command_count": len(commands),
            "executed_commands": state.executed_commands if hasattr(state, 'executed_commands') else []
        }
    except Exception as e:
        logger.error(f"Error getting task commands: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get task commands",
                "message": str(e)
            }
        )

@router.get("/api/tasks/{task_id}/vm")
async def get_task_vm(task_id: str):
    """Get the VM information for a specific task."""
    try:
        # Get components
        _, _, state_manager, _ = await get_components()
        
        state = state_manager.get_state(task_id)
        if not state:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id}
            )
        
        # Get VM info from state
        vm_id = state_manager.get_variable(task_id, "vm_id")
        if not vm_id:
            return JSONResponse(
                status_code=404,
                content={"error": "No VM found for this task", "task_id": task_id}
            )
        
        # Get VM details from VM Manager
        vm_details = await vm_manager.get_vm_details(vm_id)
        if not vm_details:
            return JSONResponse(
                status_code=404,
                content={"error": "VM details not found", "vm_id": vm_id}
            )
        
        return vm_details
    except Exception as e:
        logger.error(f"Error getting VM details: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get VM details",
                "message": str(e)
            }
        )

@router.post("/api/tasks/{task_id}/reset-vm")
async def reset_task_vm(task_id: str, request: ResetVMRequest = None):
    """Reset the VM for a specific task."""
    if request is None:
        request = ResetVMRequest()
    
    try:    
        # Get components
        _, _, state_manager, _ = await get_components()
        
        state = state_manager.get_state(task_id)
        if not state:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id}
            )
        
        # Get VM info from state
        vm_id = state_manager.get_variable(task_id, "vm_id")
        if not vm_id:
            return JSONResponse(
                status_code=404,
                content={"error": "No VM found for this task", "task_id": task_id}
            )
        
        # Reset the VM
        result = await vm_manager.reset_vm(vm_id, request.force)
        if not result:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to reset VM", "vm_id": vm_id}
            )
        
        return {
            "message": "VM reset initiated",
            "vm_id": vm_id,
            "task_id": task_id,
            "force": request.force
        }
    except Exception as e:
        logger.error(f"Error resetting VM: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to reset VM",
                "message": str(e)
            }
        )

@router.get("/api/tasks")
async def list_tasks(limit: int = 10):
    """Get a list of tasks."""
    try:
        # Get components
        _, _, state_manager, _ = await get_components()
        
        tasks = state_manager.list_tasks(limit=limit)
        
        # Add VM information to task summaries if available
        for task in tasks:
            task_id = task.get("task_id")
            if task_id:
                vm_id = state_manager.get_variable(task_id, "vm_id")
                if vm_id:
                    task["vm_id"] = vm_id
        
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        logger.error(f"Error listing tasks: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to list tasks",
                "message": str(e)
            }
        )
